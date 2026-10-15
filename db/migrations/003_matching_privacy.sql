CREATE EXTENSION IF NOT EXISTS btree_gist;
DO $$ BEGIN CREATE ROLE sed_admin NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE ngo_coordinator NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE volunteer NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE auditor NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
ALTER TABLE match ADD COLUMN IF NOT EXISTS during tstzrange;
DO $$ BEGIN ALTER TABLE match ADD CONSTRAINT volunteer_no_overlap EXCLUDE USING gist (volunteer_id WITH =, during WITH &&) WHERE (volunteer_id IS NOT NULL AND status IN ('proposed','accepted')); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
ALTER TABLE person ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS person_admin_policy ON person;
CREATE POLICY person_admin_policy ON person TO sed_admin USING(true) WITH CHECK(true);
DROP POLICY IF EXISTS person_ngo_policy ON person;
CREATE POLICY person_ngo_policy ON person TO ngo_coordinator USING(EXISTS(SELECT 1 FROM need n JOIN match m ON m.need_id=n.id JOIN ngo g ON g.id=m.resource_id WHERE n.person_id=person.id AND g.id::text=current_setting('sed.ngo_id',true))) WITH CHECK(false);
ALTER TABLE need ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS need_admin_policy ON need;
CREATE POLICY need_admin_policy ON need TO sed_admin USING(true) WITH CHECK(true);
DROP POLICY IF EXISTS need_volunteer_policy ON need;
CREATE POLICY need_volunteer_policy ON need TO volunteer USING(EXISTS(SELECT 1 FROM match m WHERE m.need_id=need.id AND m.volunteer_id=current_setting('sed.volunteer_id',true)::bigint)) WITH CHECK(false);
GRANT SELECT ON person,need,match,resource,area TO volunteer,ngo_coordinator,auditor;
GRANT ALL ON ALL TABLES IN SCHEMA public TO sed_admin;
CREATE OR REPLACE FUNCTION sed_encrypt_pii(v text) RETURNS bytea LANGUAGE sql STABLE AS $$ SELECT pgp_sym_encrypt(v,current_setting('sed.pii_key')) $$;
CREATE OR REPLACE FUNCTION sed_decrypt_pii(v bytea) RETURNS text LANGUAGE sql STABLE AS $$ SELECT pgp_sym_decrypt(v,current_setting('sed.pii_key')) $$;
CREATE OR REPLACE FUNCTION sed_release_expired(p_limit int DEFAULT 500) RETURNS int LANGUAGE plpgsql AS $$ DECLARE r record; cnt int:=0; BEGIN
 FOR r IN SELECT * FROM reservation WHERE status='held' AND expires_at<=now() ORDER BY expires_at FOR UPDATE SKIP LOCKED LIMIT p_limit LOOP
   UPDATE reservation SET status='expired' WHERE id=r.id;
   IF r.resource_id IS NOT NULL AND r.quantity>0 THEN UPDATE resource SET quantity_available=least(quantity_total,quantity_available+r.quantity) WHERE id=r.resource_id; END IF;
   UPDATE match SET status='expired' WHERE id=r.match_id AND status='proposed';
   INSERT INTO change_events(table_name,entity_id,change_kind,payload) SELECT 'need',need_id,'reservation_expired',jsonb_build_object('reservation_id',r.id) FROM match WHERE id=r.match_id;
   cnt:=cnt+1;
 END LOOP; RETURN cnt; END $$;
CREATE OR REPLACE FUNCTION sed_assign(p_need bigint,p_volunteer bigint,p_resource bigint,p_quantity int,p_score numeric,p_breakdown jsonb,p_ttl interval DEFAULT interval '15 minutes') RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE mid bigint; avail int; BEGIN
 -- Caller must begin this transaction at SERIALIZABLE; transaction isolation cannot
 -- be changed after entering a stored function.
 PERFORM 1 FROM need WHERE id=p_need AND status IN ('suspected','confirmed') FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'need unavailable'; END IF;
 IF p_resource IS NOT NULL THEN SELECT quantity_available INTO avail FROM resource WHERE id=p_resource FOR UPDATE; IF avail<p_quantity THEN RAISE EXCEPTION 'insufficient resource quantity'; END IF; UPDATE resource SET quantity_available=quantity_available-p_quantity,updated_at=now() WHERE id=p_resource; END IF;
 IF p_volunteer IS NOT NULL THEN PERFORM 1 FROM volunteer WHERE id=p_volunteer AND active FOR UPDATE; IF NOT FOUND THEN RAISE EXCEPTION 'volunteer unavailable'; END IF; END IF;
 INSERT INTO match(need_id,volunteer_id,resource_id,quantity,status,score,score_breakdown,during) VALUES(p_need,p_volunteer,p_resource,p_quantity,'proposed',p_score,p_breakdown,tstzrange(now(),now()+interval '2 hours','[)')) RETURNING id INTO mid;
 INSERT INTO reservation(match_id,resource_id,volunteer_id,quantity,expires_at) VALUES(mid,p_resource,p_volunteer,p_quantity,now()+p_ttl);
 UPDATE need SET status='matched',updated_at=now() WHERE id=p_need;
 INSERT INTO audit_log(action,entity_type,entity_id,details) VALUES('assign','match',mid,jsonb_build_object('need_id',p_need,'resource_id',p_resource,'volunteer_id',p_volunteer,'quantity',p_quantity));
 RETURN mid;
END $$;
CREATE OR REPLACE FUNCTION sed_anonymize_person(p_person bigint) RETURNS void LANGUAGE plpgsql AS $$ BEGIN
 UPDATE person SET pseudonym='erased-'||id,display_name=NULL,encrypted_phone=NULL,vulnerability_tags='{}',last_contact_at=NULL,active=false WHERE id=p_person;
 DELETE FROM person_consent WHERE person_id=p_person; INSERT INTO audit_log(action,entity_type,entity_id,details) VALUES('erase','person',p_person,'{"aggregate_statistics_preserved":true}');
END $$;
