CREATE OR REPLACE FUNCTION sed_emit_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE eid bigint; aid bigint; kind text; BEGIN
 IF TG_OP='DELETE' THEN eid:=OLD.id; aid:=to_jsonb(OLD)->>'area_id'; kind:='delete'; ELSE eid:=NEW.id; aid:=to_jsonb(NEW)->>'area_id'; kind:=lower(TG_OP); END IF;
 INSERT INTO change_events(table_name,entity_id,area_id,change_kind,payload) VALUES(TG_TABLE_NAME,eid,aid::bigint,kind,
   jsonb_strip_nulls(jsonb_build_object('id',eid,'person_id',coalesce(to_jsonb(NEW)->>'person_id',to_jsonb(OLD)->>'person_id'),'household_id',coalesce(to_jsonb(NEW)->>'household_id',to_jsonb(OLD)->>'household_id'),'area_id',aid)));
 RETURN coalesce(NEW,OLD);
END $$;
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['person','household','ngo','volunteer','resource','need','signal','area','volunteer_availability'] LOOP
 EXECUTE format('DROP TRIGGER IF EXISTS sed_change_outbox ON %I',t);
 EXECUTE format('CREATE TRIGGER sed_change_outbox AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION sed_emit_change()',t);
END LOOP; END $$;
INSERT INTO signal_type(name,default_weight,half_life,source_reliability) VALUES
('missed_checkin',.68,interval '5 days',.8),('aid_lapse',.75,interval '10 days',.85),('scheme_renewal_overdue',.6,interval '30 days',.9),('living_alone_no_contact',.55,interval '14 days',.7),('repeated_assistance',.62,interval '21 days',.85),('utility_flag',.5,interval '7 days',.8),('health_camp_absence',.4,interval '30 days',.7),('school_dropout',.7,interval '45 days',.8),('household_income_drop',.68,interval '30 days',.75),('disaster_zone_entry',.9,interval '3 days',.9)
ON CONFLICT(name) DO NOTHING;
INSERT INTO need_type(name,required_skills,sla) VALUES
('food_support',ARRAY['distribution'],interval '12 hours'),
('medical_support',ARRAY['first_aid'],interval '4 hours'),
('wellbeing_visit',ARRAY['community_visit'],interval '48 hours'),
('welfare_support',ARRAY['casework'],interval '72 hours')
ON CONFLICT(name) DO NOTHING;
CREATE UNIQUE INDEX IF NOT EXISTS need_rule_version_key ON need_rule(need_type_id,coalesce(signal_type_id,0),version);
INSERT INTO need_rule(need_type_id,threshold,min_signal_count,min_confidence)
SELECT id,.28,1,.30 FROM need_type ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS anomaly_result(id bigserial PRIMARY KEY, area_id bigint REFERENCES area(id), signal_type_id bigint REFERENCES signal_type(id), observed_rate numeric NOT NULL, baseline_rate numeric NOT NULL, z_score numeric NOT NULL, calculated_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS need_person_type_open_unique ON need(person_id,need_type_id) WHERE person_id IS NOT NULL AND status IN ('suspected','confirmed');
CREATE OR REPLACE FUNCTION sed_signal_score(p_person bigint,p_household bigint,p_need_type bigint,p_at timestamptz DEFAULT now()) RETURNS TABLE(score numeric,confidence numeric,signal_ids bigint[]) LANGUAGE sql STABLE AS $$
 WITH eligible AS (SELECT s.id,s.signal_type_id,s.occurred_at,st.default_weight,st.half_life,coalesce(s.source_reliability,st.source_reliability) reliability
   FROM signal s JOIN signal_type st ON st.id=s.signal_type_id
   WHERE (p_person IS NOT NULL AND s.person_id=p_person OR p_household IS NOT NULL AND s.household_id=p_household)
     AND (p_need_type IS NULL OR EXISTS(SELECT 1 FROM need_rule nr WHERE nr.need_type_id=p_need_type AND nr.active AND (nr.signal_type_id IS NULL OR nr.signal_type_id=s.signal_type_id)))
     AND s.occurred_at<=p_at AND s.occurred_at>p_at-interval '365 days'),
 calc AS (SELECT *,default_weight*reliability*exp(-ln(2)*extract(epoch FROM (p_at-occurred_at))/greatest(extract(epoch FROM half_life),1)) contrib FROM eligible),
 agg AS (SELECT coalesce(sum(contrib),0) raw,count(*) n,count(DISTINCT signal_type_id) diversity,coalesce(avg(reliability),0) reliability,coalesce(max(exp(-ln(2)*extract(epoch FROM (p_at-occurred_at))/greatest(extract(epoch FROM half_life),1))),0) recency,array_agg(id) ids FROM calc)
 SELECT least(1,raw/greatest(n,1))::numeric,least(1,(.3*least(n/4.0,1)+.25*least(diversity/3.0,1)+.25*recency+.2*reliability))::numeric,coalesce(ids,'{}') FROM agg $$;
CREATE OR REPLACE FUNCTION sed_recompute_person(p_person bigint) RETURNS int LANGUAGE plpgsql AS $$
DECLARE p record; r record; sc numeric; cf numeric; sids bigint[]; nid bigint; changed int:=0; BEGIN SELECT * INTO p FROM person WHERE id=p_person; IF NOT FOUND THEN RETURN 0; END IF;
 IF NOT EXISTS(SELECT 1 FROM person_consent WHERE person_id=p_person AND purpose='need_inference' AND withdrawn_at IS NULL) THEN RETURN 0; END IF;
 FOR r IN SELECT nt.id need_type_id,nr.threshold,nr.min_signal_count,nr.min_confidence FROM need_type nt JOIN need_rule nr ON nr.need_type_id=nt.id WHERE nr.active LOOP
   SELECT x.score,x.confidence,x.signal_ids INTO sc,cf,sids FROM sed_signal_score(p_person,NULL,r.need_type_id) x;
   IF cardinality(sids)>=r.min_signal_count AND sc>=r.threshold AND cf>=r.min_confidence THEN
     INSERT INTO need(person_id,need_type_id,area_id,location_id,score,confidence,status,priority,sla_due_at)
       VALUES(p_person,r.need_type_id,p.area_id,p.location_id,sc,cf,CASE WHEN cf>=.75 THEN 'confirmed'::need_status ELSE 'suspected'::need_status END,greatest(1,round(sc*100)::int),now()+interval '24 hours')
       ON CONFLICT (person_id,need_type_id) WHERE person_id IS NOT NULL AND status IN ('suspected','confirmed')
       DO UPDATE SET score=excluded.score,confidence=excluded.confidence,
         status=CASE WHEN excluded.confidence>=.75 THEN 'confirmed'::need_status ELSE need.status END,
         priority=greatest(need.priority,excluded.priority),updated_at=now() RETURNING id INTO nid;
     IF nid IS NOT NULL THEN
       changed:=changed+1;
       DELETE FROM need_signal WHERE need_id=nid AND NOT(signal_id=ANY(sids));
       INSERT INTO need_signal(need_id,signal_id,contribution)
       SELECT nid,s.id,st.default_weight*coalesce(s.source_reliability,st.source_reliability)*
          exp(-ln(2)*extract(epoch FROM (now()-s.occurred_at))/greatest(extract(epoch FROM st.half_life),1))
       FROM unnest(sids) AS ids(signal_id) JOIN signal s ON s.id=ids.signal_id JOIN signal_type st ON st.id=s.signal_type_id
       ON CONFLICT(need_id,signal_id) DO UPDATE SET contribution=excluded.contribution;
     END IF;
   END IF;
 END LOOP; RETURN changed;
END $$;
-- Work is bounded by one entity and the entity's immediate geography; SKIP LOCKED supports workers.
CREATE OR REPLACE FUNCTION sed_process_change_batch(p_limit int DEFAULT 100) RETURNS int LANGUAGE plpgsql AS $$
DECLARE ev record; affected int:=0; BEGIN
 FOR ev IN SELECT * FROM change_events WHERE processed_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT greatest(1,least(p_limit,1000)) LOOP
   IF ev.table_name='signal' THEN
     PERFORM sed_recompute_person((ev.payload->>'person_id')::bigint);
   ELSIF ev.table_name='person' THEN PERFORM sed_recompute_person(ev.entity_id);
   ELSIF ev.table_name='area' THEN
     -- Recompute only people in changed polygon or configured local radius; no full-table sweep.
     PERFORM sed_recompute_person(p.id) FROM person p JOIN location l ON l.id=p.location_id JOIN area a ON a.id=ev.area_id WHERE a.geom IS NOT NULL AND ST_DWithin(l.point,a.geom::geography,10000);
   ELSIF ev.table_name IN ('resource','volunteer','volunteer_availability') THEN
     -- Mark only nearby open compatible needs for the matcher queue; matcher consumes these IDs.
     UPDATE need SET updated_at=now() WHERE status IN ('suspected','confirmed') AND (ev.area_id IS NULL OR area_id=ev.area_id OR EXISTS(SELECT 1 FROM area a WHERE a.id=ev.area_id AND a.geom IS NOT NULL AND EXISTS(SELECT 1 FROM location l WHERE l.id=need.location_id AND ST_DWithin(l.point,a.geom::geography,10000))));
   END IF;
   UPDATE change_events SET processed_at=now(),attempts=attempts+1 WHERE id=ev.id; affected:=affected+1;
 END LOOP; RETURN affected; END $$;
CREATE OR REPLACE VIEW area_signal_anomaly AS
 WITH rates AS (SELECT area_id,signal_type_id,count(*)::numeric / greatest(count(DISTINCT occurred_at::date),1) rate FROM signal WHERE occurred_at>now()-interval '30 days' AND area_id IS NOT NULL GROUP BY area_id,signal_type_id),
 z AS (SELECT area_id,signal_type_id,rate,avg(rate) OVER(PARTITION BY signal_type_id) baseline,stddev_pop(rate) OVER(PARTITION BY signal_type_id) spread FROM rates)
 SELECT area_id,signal_type_id,rate observed_rate,baseline,CASE WHEN spread>0 THEN (rate-baseline)/spread ELSE 0 END z_score FROM z;
