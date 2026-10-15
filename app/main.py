from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from .db import connection

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
