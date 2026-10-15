from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg.errors import SerializationFailure, DeadlockDetected
import time
from .db import connection
from .matching import solve, fairness_cost

app = FastAPI(title="Silent Emergency Database", version="0.1.0")

class SignalIn(BaseModel):
    signal_type: str
    person_id: int | None = None
    household_id: int | None = None
    area_id: int | None = None
    occurred_at: str
    source: str
    idempotency_key: str
    payload: dict = Field(default_factory=dict)

class PersonIn(BaseModel):
    pseudonym: str
    display_name: str | None = None
    age_band: str | None = None
    area_id: int | None = None
    household_size: int = 1
    living_alone: bool = False
    idempotency_key: str

class HouseholdIn(BaseModel):
    pseudonym: str
    area_id: int | None = None
    household_size: int = 1
    idempotency_key: str

@app.get("/health")
def health():
    with connection() as c:
        return {"ok": c.execute("select 1").fetchone()[0] == 1}

@app.post("/signals")
def post_signal(body: SignalIn):
    with connection() as c:
        row = c.execute("""INSERT INTO signal(signal_type_id,person_id,household_id,area_id,occurred_at,source,idempotency_key,payload)
          SELECT id,%s,%s,%s,%s,%s,%s,%s FROM signal_type WHERE name=%s
          ON CONFLICT(idempotency_key) DO UPDATE SET idempotency_key=excluded.idempotency_key RETURNING id""",
          (body.person_id,body.household_id,body.area_id,body.occurred_at,body.source,body.idempotency_key,Jsonb(body.payload),body.signal_type)).fetchone()
        if row is None: raise HTTPException(404,"unknown signal type")
        return {"id":row[0],"accepted":True}

@app.post("/persons")
def create_person(body:PersonIn):
    with connection() as c:
        previous=c.execute("SELECT response FROM api_idempotency WHERE key=%s AND operation='person'",(body.idempotency_key,)).fetchone()
        if previous: return previous[0]
        row=c.execute("INSERT INTO person(pseudonym,display_name,age_band,area_id,household_size,living_alone) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(pseudonym) DO UPDATE SET pseudonym=excluded.pseudonym RETURNING id",(body.pseudonym,body.display_name,body.age_band,body.area_id,body.household_size,body.living_alone)).fetchone()
        response={'id':row[0]}
        c.execute("INSERT INTO api_idempotency(key,operation,response) VALUES(%s,'person',%s) ON CONFLICT DO NOTHING",(body.idempotency_key,Jsonb(response)))
        return response

@app.post("/households")
def create_household(body:HouseholdIn):
    with connection() as c:
        previous=c.execute("SELECT response FROM api_idempotency WHERE key=%s AND operation='household'",(body.idempotency_key,)).fetchone()
        if previous: return previous[0]
        row=c.execute("INSERT INTO household(pseudonym,area_id,household_size) VALUES(%s,%s,%s) ON CONFLICT(pseudonym) DO UPDATE SET pseudonym=excluded.pseudonym RETURNING id",(body.pseudonym,body.area_id,body.household_size)).fetchone()
        response={'id':row[0]}
        c.execute("INSERT INTO api_idempotency(key,operation,response) VALUES(%s,'household',%s) ON CONFLICT DO NOTHING",(body.idempotency_key,Jsonb(response)))
        return response

def _match_action(match_id:int,action:str):
    with connection() as c:
        row=c.execute("SELECT id,need_id,volunteer_id,resource_id,status FROM match WHERE id=%s FOR UPDATE",(match_id,)).fetchone()
        if not row: raise HTTPException(404,'match not found')
        if action=='accept':
            c.execute("UPDATE match SET status='accepted' WHERE id=%s",(match_id,)); c.execute("UPDATE reservation SET status='committed' WHERE match_id=%s AND status='held'",(match_id,))
        elif action=='reject':
            c.execute("UPDATE match SET status='rejected' WHERE id=%s",(match_id,)); c.execute("SELECT sed_release_reservation(id) FROM reservation WHERE match_id=%s AND status='held'",(match_id,)); c.execute("SELECT sed_apply_feedback(%s,'rejected')",(match_id,))
        else:
            c.execute("UPDATE match SET status='completed' WHERE id=%s",(match_id,)); c.execute("UPDATE need SET status='resolved',resolved_at=now(),updated_at=now() WHERE id=%s",(row[1],)); c.execute("SELECT sed_apply_feedback(%s,'success')",(match_id,))
        return {'id':match_id,'status':{'accept':'accepted','reject':'rejected','complete':'completed'}[action]}

@app.post("/matches/{match_id}/accept")
def accept_match(match_id:int): return _match_action(match_id,'accept')
@app.post("/matches/{match_id}/reject")
def reject_match(match_id:int): return _match_action(match_id,'reject')
@app.post("/matches/{match_id}/complete")
def complete_match(match_id:int): return _match_action(match_id,'complete')

@app.post("/matches/assign")
def assign(need_id:int,volunteer_id:int|None=None,resource_id:int|None=None,quantity:int=0):
    for attempt in range(5):
        try:
            with connection('serializable') as c:
                score=c.execute("SELECT coalesce(score,0) FROM need WHERE id=%s",(need_id,)).fetchone()
                if not score: raise HTTPException(404,'need not found')
                match_id=c.execute("SELECT sed_assign(%s,%s,%s,%s,%s,%s::jsonb)",(need_id,volunteer_id,resource_id,quantity,score[0],'{"source":"api"}')).fetchone()[0]
                return {'id':match_id,'status':'proposed'}
        except (SerializationFailure,DeadlockDetected):
            if attempt==4: raise HTTPException(409,'assignment contention; retry request')
            time.sleep(.02*(attempt+1))

@app.get("/needs")
def get_needs(status: str | None = None, area: int | None = None):
    with connection() as c:
        rows=c.execute("SELECT id,person_id,household_id,need_type_id,status,score,confidence,priority FROM need WHERE (%s IS NULL OR status=%s) AND (%s IS NULL OR area_id=%s) ORDER BY priority DESC LIMIT 500",(status,status,area,area)).fetchall()
        return [dict(zip(("id","person_id","household_id","need_type_id","status","score","confidence","priority"),r)) for r in rows]

@app.get("/needs/{need_id}/history")
def need_history(need_id:int):
    with connection() as c:
        return c.execute("SELECT status,score,confidence,valid_from,valid_to FROM need_history WHERE need_id=%s ORDER BY valid_from",(need_id,)).fetchall()

@app.get("/audit/verify")
def verify_audit():
    with connection() as c: return {"valid":c.execute("SELECT verify_audit_chain()").fetchone()[0]}

@app.get('/imports/{batch_id}/report')
def import_report(batch_id:int):
    with connection() as c:
        row=c.execute("SELECT report,status,row_count,accepted_count,rejected_count FROM import_batch WHERE id=%s",(batch_id,)).fetchone()
        if not row: raise HTTPException(404,'import batch not found')
        return {'report':row[0],'status':row[1],'rows':row[2],'accepted':row[3],'rejected':row[4]}

@app.post("/worker/drain")
def drain(limit:int=100):
    with connection() as c: return {"processed":c.execute("SELECT sed_process_change_batch(%s)",(limit,)).fetchone()[0]}

@app.get("/matches")
def matches():
    with connection() as c:
        return c.execute("SELECT id,need_id,volunteer_id,resource_id,status,score,score_breakdown,created_at FROM match ORDER BY created_at DESC LIMIT 500").fetchall()

@app.get("/needs/{need_id}/explain")
def explain(need_id:int):
    with connection() as c:
        row=c.execute("SELECT n.id,n.score,n.confidence,n.status,coalesce(jsonb_agg(jsonb_build_object('signal_id',ns.signal_id,'contribution',ns.contribution)) FILTER(WHERE ns.signal_id IS NOT NULL),'[]'::jsonb) signals FROM need n LEFT JOIN need_signal ns ON ns.need_id=n.id WHERE n.id=%s GROUP BY n.id",(need_id,)).fetchone()
        if row is None: raise HTTPException(404,'need not found')
        return {"need_id":row[0],"score":row[1],"confidence":row[2],"status":row[3],"signals":row[4]}

@app.get("/resources/idle")
def idle_resources(days:int=30):
    with connection() as c:
        return c.execute("SELECT r.id,rt.name,r.quantity_available,r.updated_at FROM resource r JOIN resource_type rt USING(resource_type_id) WHERE r.quantity_available>0 AND r.updated_at<now()-(%s*interval '1 day') ORDER BY r.updated_at",(days,)).fetchall()

@app.get("/areas/{area_id}/heatmap")
def heatmap(area_id:int):
    with connection() as c:
        return c.execute("SELECT a.id,a.name,count(n.id) FILTER(WHERE n.status IN ('suspected','confirmed')) density FROM area a LEFT JOIN need n ON n.area_id=a.id WHERE a.id=%s GROUP BY a.id",(area_id,)).fetchone()

@app.get("/metrics")
def metrics():
    with connection() as c:
        return c.execute("SELECT (SELECT avg(extract(epoch FROM (m.created_at-n.detected_at))/3600) FROM match m JOIN need n ON n.id=m.need_id WHERE m.status='completed') mean_response_hours,(SELECT count(*) FROM resource WHERE quantity_available>0 AND updated_at<now()-interval '30 days') idle_resource_rows,(SELECT count(*) FILTER(WHERE status='resolved')::numeric/greatest(count(*),1) FROM need) coverage_ratio").fetchone()

@app.post("/simulate")
def simulate():
    with connection() as c:
        rows=c.execute("SELECT need_id,volunteer_id,distance_m,priority,skill_hits,reliability,starvation,zone_service,expiry_urgency FROM sed_candidate_cost WHERE in_radius ORDER BY need_id,volunteer_id").fetchall()
        need_ids=sorted({r[0] for r in rows}); vol_ids=sorted({r[1] for r in rows}); weights={'distance':.35,'priority':.3,'skill':.2,'reliability':.15,'starvation':.2,'zone_service':.2,'expiry':.15}
        costs=[[float('inf') for _ in vol_ids] for _ in need_ids]
        for n,v,d,p,s,rel,star,zone,exp in rows:
            costs[need_ids.index(n)][vol_ids.index(v)]=fairness_cost(d,p,s,rel,star,zone,exp,weights)
        pairs,total=solve(costs)
        return {'assignments':[{'need_id':need_ids[i],'volunteer_id':vol_ids[j]} for i,j in pairs],'total_cost':total,'projected_assignment_count':len(pairs),'simulation_only':True}
