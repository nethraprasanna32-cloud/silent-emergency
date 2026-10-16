"""Config-driven local CSV/XLSX/JSON/GeoJSON importer. Data is never sent externally."""
import argparse, csv, hashlib, json, os
from pathlib import Path
import yaml
from psycopg.types.json import Jsonb

def load_rows(path: Path):
    suffix=path.suffix.lower()
    if suffix=='.csv':
        with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
    if suffix=='.json':
        data=json.loads(path.read_text(encoding='utf-8')); return data if isinstance(data,list) else data.get('features',data.get('records',[data]))
    if suffix=='.geojson':
        data=json.loads(path.read_text(encoding='utf-8')); return data.get('features',[])
    if suffix in ('.xlsx','.xls'):
        import pandas as pd
        return pd.read_excel(path).where(lambda x:x.notna(),None).to_dict(orient='records')
    raise ValueError(f'unsupported format: {suffix}')

def transform(value, spec):
    if value in (None,''):
        if 'default' in spec: return spec['default']
        if spec.get('required'): raise ValueError('required value is empty')
    op=spec.get('transform')
    if op=='strip' and value is not None: value=str(value).strip()
    elif op=='lower' and value is not None: value=str(value).strip().lower()
    elif op=='int' and value is not None: value=int(value)
    elif op=='bool' and value is not None: value=str(value).strip().lower() in ('true','1','yes','y')
    return value

def process_source(source: str, path: Path, dry_run: bool=False):
    mapping_path=Path(__file__).parent/'mappings'/f'{source}.yml'
    if not mapping_path.exists(): raise SystemExit(f'no mapping: {mapping_path}')
    mapping=yaml.safe_load(mapping_path.read_text(encoding='utf-8')); rows=load_rows(path)
    errs=[]; accepted=[]; normalized_by_row={}
    for i,row in enumerate(rows,1):
        src=row.get('properties',row) if isinstance(row,dict) else {}
        result={}
        try:
            for col,spec in mapping.get('columns',{}).items(): result[spec['target']]=transform(src.get(col),spec)
            accepted.append(result); normalized_by_row[i]=result
        except Exception as e: errs.append({'row':i,'reason':str(e),'raw':row})
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    report={'source':source,'rows':len(rows),'accepted':len(accepted),'rejected':len(errs),'sha256':digest,'dry_run':dry_run}
    os.makedirs('reports',exist_ok=True)
    out=Path('reports')/f"{source}-{report['sha256'][:12]}.json"
    if not dry_run:
        from app.db import connection
        with connection() as conn:
            existing=conn.execute("SELECT id,report FROM import_batch WHERE source=%s AND file_hash=%s",(source,digest)).fetchone()
            if existing:
                old=existing[1]
                if old: return {**old,'batch_id':existing[0]},[]
                batch=existing[0]
            else:
                batch=conn.execute("INSERT INTO import_batch(source,file_name,file_hash,status,row_count,accepted_count,rejected_count) VALUES(%s,%s,%s,'staged',%s,%s,%s) RETURNING id",(source,path.name,digest,len(rows),len(accepted),len(errs))).fetchone()[0]
            for i,row in enumerate(rows,1):
                conn.execute("INSERT INTO stg_record(batch_id,row_number,source_record,normalized_record,status) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(batch_id,row_number) DO NOTHING",(batch,i,Jsonb(row),Jsonb(normalized_by_row[i]) if i in normalized_by_row else None,'accepted' if i in normalized_by_row else 'rejected'))
            for e in errs: conn.execute("INSERT INTO import_row_error(batch_id,row_number,reason,raw_value) VALUES(%s,%s,%s,%s)",(batch,e['row'],e['reason'],json.dumps(e['raw'],default=str)))
            report['batch_id']=batch
            # Promote validated rows into the normalized core tables. Natural keys
            # make re-imports idempotent while keeping the staging record for audit.
            if source == 'ngos':
                for row in accepted:
                    conn.execute("""INSERT INTO ngo(name,registration_id,ngo_type,state,district,address,capacity)
                      VALUES(%s,%s,%s,%s,%s,%s,%s)
                      ON CONFLICT(registration_id) DO UPDATE SET name=EXCLUDED.name,ngo_type=EXCLUDED.ngo_type,
                        state=EXCLUDED.state,district=EXCLUDED.district,address=EXCLUDED.address,capacity=EXCLUDED.capacity""",
                      (row.get('name'),row.get('registration_id') or None,row.get('ngo_type'),row.get('state'),row.get('district'),row.get('address'),row.get('capacity') or 0))
            elif source == 'volunteers':
                for row in accepted:
                    conn.execute("""INSERT INTO volunteer(person_name,pseudonym,verified,mode)
                      VALUES(%s,%s,%s,%s) ON CONFLICT(pseudonym) DO UPDATE SET person_name=EXCLUDED.person_name,
                      verified=EXCLUDED.verified,mode=EXCLUDED.mode""",
                      (row.get('person_name'),row.get('pseudonym'),row.get('verified',False),row.get('mode') or 'walk'))
            elif source == 'resources':
                for row in accepted:
                    rt=conn.execute("""INSERT INTO resource_type(name,category,unit) VALUES(%s,%s,'unit')
                      ON CONFLICT(name) DO UPDATE SET category=EXCLUDED.category RETURNING id""",
                      (row.get('resource_type'),row.get('resource_type'))).fetchone()[0]
                    qty=row.get('quantity_total') or 0
                    conn.execute("""INSERT INTO resource(resource_type_id,quantity_total,quantity_available,expires_at,perishable)
                      VALUES(%s,%s,%s,NULLIF(%s,'')::timestamptz,%s)
                      ON CONFLICT DO NOTHING""",(rt,qty,qty,row.get('expires_at'),row.get('perishable',False)))
            conn.execute("UPDATE import_batch SET status='staged',report=%s,completed_at=now() WHERE id=%s",(Jsonb(report),batch))
    out.write_text(json.dumps({'report':report,'errors':errs},indent=2,default=str),encoding='utf-8')
    return report,errs

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--source',required=True); parser.add_argument('--file',required=True); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    report,errs=process_source(args.source,Path(args.file),args.dry_run)
    print(json.dumps(report));
    if not args.dry_run: print(f"Staged import batch {report.get('batch_id')} (core-entity upsert still requires source-specific handlers).")

if __name__=='__main__': main()
