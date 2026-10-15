-- Feature components used by bounded delta matching; optimizer orchestration is in SQL/API.
CREATE TABLE IF NOT EXISTS area_service_stat(area_id bigint PRIMARY KEY REFERENCES area(id), served_30d int NOT NULL DEFAULT 0 CHECK(served_30d>=0), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS need_starvation(need_id bigint PRIMARY KEY REFERENCES need(id) ON DELETE CASCADE, waiting_since timestamptz NOT NULL DEFAULT now(), last_offered_at timestamptz);
CREATE TABLE IF NOT EXISTS matching_parameters(id boolean PRIMARY KEY DEFAULT true CHECK(id), fairness_weight numeric NOT NULL DEFAULT .2 CHECK(fairness_weight BETWEEN 0 AND 1), expiry_weight numeric NOT NULL DEFAULT .15 CHECK(expiry_weight BETWEEN 0 AND 1), distance_weight numeric NOT NULL DEFAULT .35 CHECK(distance_weight BETWEEN 0 AND 1), priority_weight numeric NOT NULL DEFAULT .3 CHECK(priority_weight BETWEEN 0 AND 1), max_radius_m int NOT NULL DEFAULT 50000 CHECK(max_radius_m>0), volunteer_speed_kmh jsonb NOT NULL DEFAULT '{"walk":4,"bike":12,"car":30}');
INSERT INTO matching_parameters(id) VALUES(true) ON CONFLICT DO NOTHING;
CREATE OR REPLACE VIEW sed_candidate_cost AS
 SELECT n.id need_id,v.id volunteer_id,r.id resource_id,
   coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)::numeric distance_m,
   n.priority, coalesce((SELECT count(*) FROM volunteer_skill vs WHERE vs.volunteer_id=v.id AND vs.skill=ANY(nt.required_skills)),0)::numeric skill_hits,
   CASE WHEN r.expires_at IS NULL THEN 0 ELSE greatest(0,1-extract(epoch FROM (r.expires_at-now()))/(30*86400)) END::numeric expiry_urgency,
   coalesce(v.acceptance_rate,0)*coalesce(v.completion_rate,0)::numeric reliability,
   least(1,extract(epoch FROM (now()-coalesce(ns.waiting_since,n.detected_at)))/(30*86400))::numeric starvation,
   coalesce((SELECT served_30d FROM area_service_stat WHERE area_id=n.area_id),0)::numeric zone_service,
   (coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)/1000.0 / nullif((mp.volunteer_speed_kmh->>v.mode)::numeric,0)*60)::numeric eta_minutes,
   (coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)<=mp.max_radius_m) in_radius
 FROM need n JOIN need_type nt ON nt.id=n.need_type_id JOIN volunteer v ON v.active
 CROSS JOIN matching_parameters mp
 LEFT JOIN location nl ON nl.id=n.location_id LEFT JOIN area na ON na.id=n.area_id
 LEFT JOIN location vl ON vl.id=v.location_id LEFT JOIN area va ON va.id=v.home_area_id
 LEFT JOIN need_starvation ns ON ns.need_id=n.id
 LEFT JOIN resource r ON r.resource_type_id=nt.resource_type_id AND r.quantity_available>0
 WHERE n.status IN ('suspected','confirmed');
CREATE OR REPLACE FUNCTION sed_release_reservation(p_id bigint) RETURNS boolean LANGUAGE plpgsql AS $$ DECLARE r reservation%rowtype; BEGIN
 SELECT * INTO r FROM reservation WHERE id=p_id AND status='held' FOR UPDATE; IF NOT FOUND THEN RETURN false; END IF;
 UPDATE reservation SET status='released' WHERE id=p_id;
 IF r.resource_id IS NOT NULL AND r.quantity>0 THEN UPDATE resource SET quantity_available=least(quantity_total,quantity_available+r.quantity) WHERE id=r.resource_id; END IF;
 UPDATE match SET status='cancelled' WHERE id=r.match_id AND status='proposed';
 RETURN true; END $$;
