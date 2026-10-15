from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
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
          (body.person_id,body.household_id,body.area_id,body.occurred_at,body.source,body.idempotency_key,body.payload,body.signal_type)).fetchone()
        if row is None: raise HTTPException(404,"unknown signal type")
        return {"id":row[0],"accepted":True}

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
