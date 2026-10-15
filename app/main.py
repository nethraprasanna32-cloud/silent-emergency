from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pathlib import Path
import os
import hashlib
import json
from uuid import uuid4
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg.errors import SerializationFailure, DeadlockDetected
from psycopg.errors import UniqueViolation, CheckViolation, ForeignKeyViolation, OperationalError
import time
from .db import connection
from .matching import solve, fairness_cost

app = FastAPI(title="Silent Emergency Database API", version="1.0.0", description="PostgreSQL-backed silent-need inference and assistance workflow API.", contact={"name":"SED API"})
origins=[v.strip() for v in os.getenv('SED_CORS_ORIGINS','http://localhost:3000,http://localhost:5173').split(',') if v.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['GET','POST','PATCH','OPTIONS'],allow_headers=['*'])

@app.get('/',include_in_schema=False)
def root():
    return {'service':'Silent Emergency Database API','api_version':'1','openapi':'/openapi.json','docs':'/docs','health':'/health'}

@app.exception_handler(OperationalError)
async def database_unavailable(_request, _exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503,content={'error':{'code':'database_unavailable','message':'Database is unavailable; retry shortly.'}})

@app.exception_handler(UniqueViolation)
async def duplicate_write(_request, _exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409,content={'error':{'code':'conflict','message':'The record conflicts with an existing value.'}})

@app.exception_handler(CheckViolation)
@app.exception_handler(ForeignKeyViolation)
async def invalid_write(_request, _exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422,content={'error':{'code':'invalid_record','message':'The record violates a data constraint.'}})

@app.middleware('http')
async def api_version_header(request, call_next):
    response=await call_next(request)
    response.headers['X-SED-API-Version']='1'
    return response

def _json_rows(cur):
    names=[c.name for c in cur.description]
    return [dict(zip(names,row)) for row in cur.fetchall()]

def _body_hash(body):
    serialized=json.dumps(body,sort_keys=True,separators=(',',':'),default=lambda x:x.isoformat() if hasattr(x,'isoformat') else str(x))
    return hashlib.sha256(serialized.encode()).hexdigest()

def _idempotency_get(c,key,operation,body):
    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
    row=c.execute('SELECT operation,request_hash,response FROM api_idempotency WHERE key=%s',(key,)).fetchone()
    if not row:return None
    if row[0]!=operation or row[1]!=_body_hash(body): raise HTTPException(409,'idempotency key was already used with a different operation or payload')
    return row[2]

def _idempotency_put(c,key,operation,body,response):
    c.execute('INSERT INTO api_idempotency(key,operation,request_hash,response) VALUES(%s,%s,%s,%s)',(key,operation,_body_hash(body),Jsonb(response)))

class SignalIn(BaseModel):
    signal_type: str
    person_id: int | None = None
    household_id: int | None = None
    area_id: int | None = None
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=200)
    payload: dict = Field(default_factory=dict)

class PersonIn(BaseModel):
    pseudonym: str
    display_name: str | None = None
    age_band: str | None = None
    area_id: int | None = None
    household_size: int = 1
    living_alone: bool = False
    inference_consent: bool = False
    idempotency_key: str

class HouseholdIn(BaseModel):
    pseudonym: str
    area_id: int | None = None
    household_size: int = 1
    idempotency_key: str

class ResourcePatch(BaseModel):
    quantity_available: int | None = Field(default=None, ge=0)
    expires_at: datetime | None = None

class AvailabilityPatch(BaseModel):
    start: datetime
    end: datetime

class ConsentIn(BaseModel):
    purpose: str = Field(min_length=1, max_length=100)
    granted: bool

class MatchActionIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=200)

class AssignmentIn(BaseModel):
    need_id: int = Field(gt=0)
    volunteer_id: int | None = Field(default=None,gt=0)
    resource_id: int | None = Field(default=None,gt=0)
    quantity: int = Field(default=0,ge=0)
    idempotency_key: str = Field(min_length=8,max_length=200)

@app.get("/health")
def health():
    try:
        with connection() as c: return {"ok": c.execute("select 1").fetchone()[0] == 1, "database":"available"}
    except Exception as exc:
        return {"ok":False,"database":"unavailable","error":type(exc).__name__}

@app.post("/signals")
def post_signal(body: SignalIn):
    with connection() as c:
        cached=_idempotency_get(c,body.idempotency_key,'signal',body.model_dump(mode='json'))
        if cached is not None:return cached
        row = c.execute("""INSERT INTO signal(signal_type_id,person_id,household_id,area_id,occurred_at,source,idempotency_key,payload)
          SELECT id,%s,%s,%s,%s,%s,%s,%s FROM signal_type WHERE name=%s
          ON CONFLICT(idempotency_key) DO UPDATE SET idempotency_key=excluded.idempotency_key RETURNING id""",
          (body.person_id,body.household_id,body.area_id,body.occurred_at,body.source,body.idempotency_key,Jsonb(body.payload),body.signal_type)).fetchone()
        if row is None: raise HTTPException(404,"unknown signal type")
        response={"id":row[0],"accepted":True}; _idempotency_put(c,body.idempotency_key,'signal',body.model_dump(mode='json'),response)
        return response

@app.post("/persons")
def create_person(body:PersonIn):
    with connection() as c:
        cached=_idempotency_get(c,body.idempotency_key,'person',body.model_dump(mode='json'))
        if cached is not None:return cached
        row=c.execute("INSERT INTO person(pseudonym,display_name,age_band,area_id,household_size,living_alone) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(pseudonym) DO UPDATE SET pseudonym=excluded.pseudonym RETURNING id",(body.pseudonym,body.display_name,body.age_band,body.area_id,body.household_size,body.living_alone)).fetchone()
        if body.inference_consent:
            c.execute("INSERT INTO person_consent(person_id,purpose) VALUES(%s,'need_inference')",(row[0],))
        response={'id':row[0],'inference_consent':body.inference_consent}
        _idempotency_put(c,body.idempotency_key,'person',body.model_dump(mode='json'),response)
        return response

@app.post("/households")
def create_household(body:HouseholdIn):
    with connection() as c:
        cached=_idempotency_get(c,body.idempotency_key,'household',body.model_dump(mode='json'))
        if cached is not None:return cached
        row=c.execute("INSERT INTO household(pseudonym,area_id,household_size) VALUES(%s,%s,%s) ON CONFLICT(pseudonym) DO UPDATE SET pseudonym=excluded.pseudonym RETURNING id",(body.pseudonym,body.area_id,body.household_size)).fetchone()
        response={'id':row[0]}
        _idempotency_put(c,body.idempotency_key,'household',body.model_dump(mode='json'),response)
        return response

def _match_action(match_id:int,action:str,idempotency_key:str):
    with connection() as c:
        request={'match_id':match_id}
        cached=_idempotency_get(c,idempotency_key,f'match_{action}',request)
        if cached is not None:return cached
        row=c.execute("SELECT id,need_id,volunteer_id,resource_id,status FROM match WHERE id=%s FOR UPDATE",(match_id,)).fetchone()
        if not row: raise HTTPException(404,'match not found')
        if row[4] not in (('proposed','accepted') if action in ('accept','reject') else ('accepted',)):
            raise HTTPException(409,f"cannot {action} a match in {row[4]} state")
        if action=='accept':
            c.execute("UPDATE match SET status='accepted' WHERE id=%s",(match_id,)); c.execute("UPDATE reservation SET status='committed' WHERE match_id=%s AND status='held'",(match_id,))
        elif action=='reject':
            c.execute("UPDATE match SET status='rejected' WHERE id=%s",(match_id,)); c.execute("SELECT sed_release_reservation(id) FROM reservation WHERE match_id=%s AND status='held'",(match_id,)); c.execute("SELECT sed_apply_feedback(%s,'rejected')",(match_id,))
        else:
            c.execute("UPDATE match SET status='completed' WHERE id=%s",(match_id,)); c.execute("UPDATE need SET status='resolved',resolved_at=now(),updated_at=now() WHERE id=%s",(row[1],)); c.execute("SELECT sed_apply_feedback(%s,'success')",(match_id,))
        response={'id':match_id,'status':{'accept':'accepted','reject':'rejected','complete':'completed'}[action]}
        _idempotency_put(c,idempotency_key,f'match_{action}',request,response)
        return response

@app.post("/matches/{match_id}/accept")
def accept_match(match_id:int,body:MatchActionIn): return _match_action(match_id,'accept',body.idempotency_key)
@app.post("/matches/{match_id}/reject")
def reject_match(match_id:int,body:MatchActionIn): return _match_action(match_id,'reject',body.idempotency_key)
@app.post("/matches/{match_id}/complete")
def complete_match(match_id:int,body:MatchActionIn): return _match_action(match_id,'complete',body.idempotency_key)

@app.patch('/resources/{resource_id}')
def patch_resource(resource_id:int,body:ResourcePatch,idempotency_key:str=Header(alias='Idempotency-Key')):
    changes={k:v for k,v in body.model_dump(exclude_unset=True).items()}
    if not changes: raise HTTPException(422,'provide quantity_available or expires_at')
    with connection() as c:
        payload=body.model_dump(mode='json',exclude_unset=True)
        cached=_idempotency_get(c,idempotency_key,'resource_patch',{'resource_id':resource_id,**payload})
        if cached is not None:return cached
        row=c.execute("SELECT quantity_total FROM resource WHERE id=%s FOR UPDATE",(resource_id,)).fetchone()
        if row is None: raise HTTPException(404,'resource not found')
        if 'quantity_available' in changes and changes['quantity_available']>row[0]: raise HTTPException(422,'available quantity cannot exceed total')
        sets=[]; params=[]
        for col,val in changes.items(): sets.append(f'{col}=%s'); params.append(val)
        params.extend([resource_id])
        cur=c.execute(f"UPDATE resource SET {','.join(sets)},updated_at=now() WHERE id=%s RETURNING id,quantity_available,expires_at",params)
        r=cur.fetchone(); response={'id':r[0],'quantity_available':r[1],'expires_at':r[2]}
        _idempotency_put(c,idempotency_key,'resource_patch',{'resource_id':resource_id,**payload},response)
        return response

@app.patch('/volunteers/{volunteer_id}/availability')
def patch_availability(volunteer_id:int,body:AvailabilityPatch,idempotency_key:str=Header(alias='Idempotency-Key')):
    if body.end<=body.start: raise HTTPException(422,'availability end must follow start')
    with connection() as c:
        payload={'volunteer_id':volunteer_id,**body.model_dump(mode='json')}
        cached=_idempotency_get(c,idempotency_key,'availability_patch',payload)
        if cached is not None:return cached
        if not c.execute("SELECT 1 FROM volunteer WHERE id=%s AND active FOR UPDATE",(volunteer_id,)).fetchone(): raise HTTPException(404,'active volunteer not found')
        row=c.execute("INSERT INTO volunteer_availability(volunteer_id,during) VALUES(%s,tstzrange(%s,%s,'[)')) RETURNING id",(volunteer_id,body.start,body.end)).fetchone()
        response={'id':row[0],'volunteer_id':volunteer_id,'start':body.start,'end':body.end}
        _idempotency_put(c,idempotency_key,'availability_patch',payload,response)
        return response

@app.post('/persons/{person_id}/consent')
def update_consent(person_id:int,body:ConsentIn,idempotency_key:str=Header(alias='Idempotency-Key')):
    with connection() as c:
        payload={'person_id':person_id,**body.model_dump(mode='json')}
        cached=_idempotency_get(c,idempotency_key,'consent',payload)
        if cached is not None:return cached
        if not c.execute("SELECT 1 FROM person WHERE id=%s FOR UPDATE",(person_id,)).fetchone(): raise HTTPException(404,'person not found')
        if body.granted:
            c.execute("INSERT INTO person_consent(person_id,purpose) VALUES(%s,%s)",(person_id,body.purpose))
        else:
            c.execute("UPDATE person_consent SET withdrawn_at=now() WHERE person_id=%s AND purpose=%s AND withdrawn_at IS NULL",(person_id,body.purpose))
        response={'person_id':person_id,'purpose':body.purpose,'granted':body.granted}
        _idempotency_put(c,idempotency_key,'consent',payload,response)
        return response

@app.post("/matches/assign")
def assign(body:AssignmentIn):
    for attempt in range(5):
        try:
            with connection('serializable') as c:
                request=body.model_dump(mode='json',exclude={'idempotency_key'})
                cached=_idempotency_get(c,body.idempotency_key,'assignment',request)
                if cached is not None:return cached
                score=c.execute("SELECT coalesce(score,0) FROM need WHERE id=%s",(body.need_id,)).fetchone()
                if not score: raise HTTPException(404,'need not found')
                match_id=c.execute("SELECT sed_assign(%s,%s,%s,%s,%s,%s::jsonb)",(body.need_id,body.volunteer_id,body.resource_id,body.quantity,score[0],'{"source":"api"}')).fetchone()[0]
                response={'id':match_id,'status':'proposed'}
                _idempotency_put(c,body.idempotency_key,'assignment',request,response)
                return response
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
        return _json_rows(c.execute("SELECT status,score,confidence,valid_from,valid_to FROM need_history WHERE need_id=%s ORDER BY valid_from",(need_id,)))

@app.get("/audit/verify")
def verify_audit():
    with connection() as c: return {"valid":c.execute("SELECT verify_audit_chain()").fetchone()[0]}

@app.get('/audit')
def get_audit(after_id:int=0,limit:int=100):
    if not 1<=limit<=500: raise HTTPException(422,'limit must be between 1 and 500')
    with connection() as c:
        return _json_rows(c.execute("SELECT id,actor,action,entity_type,entity_id,details,previous_hash,row_hash,created_at FROM audit_log WHERE id>%s ORDER BY id LIMIT %s",(after_id,limit)))

@app.get('/imports/{batch_id}/report')
def import_report(batch_id:int):
    with connection() as c:
        row=c.execute("SELECT report,status,row_count,accepted_count,rejected_count FROM import_batch WHERE id=%s",(batch_id,)).fetchone()
        if not row: raise HTTPException(404,'import batch not found')
        return {'report':row[0],'status':row[1],'rows':row[2],'accepted':row[3],'rejected':row[4]}

@app.post('/imports',status_code=202)
async def import_upload(source:str=Form(...),file:UploadFile=File(...)):
    from importers.run import process_source
    mapping_dir=Path('importers/mappings')
    if source not in {p.stem for p in mapping_dir.glob('*.yml')}: raise HTTPException(422,'unsupported import source')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.csv','.xlsx','.xls','.json','.geojson'): raise HTTPException(415,'supported formats are CSV, XLSX, JSON and GeoJSON')
    target_dir=Path('data/incoming'); target_dir.mkdir(parents=True,exist_ok=True)
    path=target_dir/f'{uuid4().hex}{suffix}'; size=0
    try:
        with path.open('wb') as dest:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>50*1024*1024: raise HTTPException(413,'maximum import size is 50 MiB')
                dest.write(chunk)
        report,errors=process_source(source,path,False)
        public_errors=[{k:e[k] for k in ('row','column','reason') if k in e} for e in errors]
        return {'batch_id':report.get('batch_id'),'status':'staged','report':report,'errors':public_errors}
    except HTTPException: raise
    except (ValueError,UnicodeError) as exc: raise HTTPException(422,'import file could not be parsed or validated') from exc
    finally:
        await file.close()
        path.unlink(missing_ok=True)

@app.post("/worker/drain")
def drain(limit:int=100):
    with connection() as c: return {"processed":c.execute("SELECT sed_process_change_batch(%s)",(limit,)).fetchone()[0]}

@app.get("/matches")
def matches():
    with connection() as c:
        return _json_rows(c.execute("SELECT id,need_id,volunteer_id,resource_id,status,score,score_breakdown,created_at FROM match ORDER BY created_at DESC LIMIT 500"))

@app.get("/needs/{need_id}/explain")
def explain(need_id:int):
    with connection() as c:
        row=c.execute("SELECT n.id,n.score,n.confidence,n.status,coalesce(jsonb_agg(jsonb_build_object('signal_id',ns.signal_id,'contribution',ns.contribution)) FILTER(WHERE ns.signal_id IS NOT NULL),'[]'::jsonb) signals FROM need n LEFT JOIN need_signal ns ON ns.need_id=n.id WHERE n.id=%s GROUP BY n.id",(need_id,)).fetchone()
        if row is None: raise HTTPException(404,'need not found')
        return {"need_id":row[0],"score":row[1],"confidence":row[2],"status":row[3],"signals":row[4]}

@app.get("/resources/idle")
def idle_resources(days:int=30):
    with connection() as c:
        return _json_rows(c.execute("SELECT r.id,rt.name,r.quantity_available,r.updated_at FROM resource r JOIN resource_type rt USING(resource_type_id) WHERE r.quantity_available>0 AND r.updated_at<now()-(%s*interval '1 day') ORDER BY r.updated_at",(days,)))

@app.get("/areas/{area_id}/heatmap")
def heatmap(area_id:int):
    with connection() as c:
        row=c.execute("SELECT a.id,a.name,count(n.id) FILTER(WHERE n.status IN ('suspected','confirmed')) density FROM area a LEFT JOIN need n ON n.area_id=a.id WHERE a.id=%s GROUP BY a.id",(area_id,)).fetchone()
        if row is None: raise HTTPException(404,'area not found')
        return {'area_id':row[0],'name':row[1],'silent_need_count':row[2]}

@app.get("/metrics")
def metrics():
    with connection() as c:
        r=c.execute("SELECT (SELECT avg(extract(epoch FROM (m.created_at-n.detected_at))/3600) FROM match m JOIN need n ON n.id=m.need_id WHERE m.status='completed') mean_response_hours,(SELECT count(*) FROM resource WHERE quantity_available>0 AND updated_at<now()-interval '30 days') idle_resource_rows,(SELECT count(*) FILTER(WHERE status='resolved')::numeric/greatest(count(*),1) FROM need) coverage_ratio").fetchone()
        return {'mean_response_hours':r[0],'idle_resource_rows':r[1],'coverage_ratio':r[2]}

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
