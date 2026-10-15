CREATE TABLE IF NOT EXISTS api_idempotency (key text PRIMARY KEY, operation text NOT NULL, response jsonb, created_at timestamptz NOT NULL DEFAULT now());
CREATE OR REPLACE FUNCTION sed_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$;
DROP TRIGGER IF EXISTS audit_no_mutation ON audit_log;
CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION sed_audit_immutable();
DROP POLICY IF EXISTS person_ngo_policy ON person;
CREATE POLICY person_ngo_policy ON person TO ngo_coordinator USING(EXISTS(SELECT 1 FROM need n JOIN match m ON m.need_id=n.id JOIN resource r ON r.id=m.resource_id WHERE n.person_id=person.id AND r.owner_ngo_id::text=current_setting('sed.ngo_id',true))) WITH CHECK(false);
CREATE OR REPLACE FUNCTION sed_escalate_sla(p_limit int DEFAULT 200) RETURNS int LANGUAGE plpgsql AS $$ DECLARE n int; BEGIN
 WITH due AS (SELECT id FROM need WHERE status IN ('suspected','confirmed') AND sla_due_at<now() ORDER BY sla_due_at FOR UPDATE SKIP LOCKED LIMIT p_limit)
 UPDATE need x SET priority=least(100,priority+10),sla_due_at=now()+interval '24 hours',updated_at=now() FROM due WHERE x.id=due.id;
 GET DIAGNOSTICS n=ROW_COUNT; RETURN n; END $$;
CREATE OR REPLACE FUNCTION sed_apply_feedback(p_match bigint,p_outcome text) RETURNS void LANGUAGE plpgsql AS $$ DECLARE v bigint; BEGIN
 INSERT INTO assistance_history(match_id,outcome) VALUES(p_match,p_outcome);
 SELECT volunteer_id INTO v FROM match WHERE id=p_match;
 IF v IS NOT NULL THEN
   UPDATE volunteer SET acceptance_rate=greatest(0,least(1,.9*acceptance_rate+.1*CASE WHEN p_outcome<>'rejected' THEN 1 ELSE 0 END)),completion_rate=greatest(0,least(1,.9*completion_rate+.1*CASE WHEN p_outcome='success' THEN 1 ELSE 0 END)),reliability_updated_at=now() WHERE id=v;
 END IF;
 INSERT INTO audit_log(action,entity_type,entity_id,details) VALUES('feedback','match',p_match,jsonb_build_object('outcome',p_outcome));
END $$;
