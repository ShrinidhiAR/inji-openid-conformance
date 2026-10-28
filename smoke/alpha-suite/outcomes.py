"""Allowlist actual suite outcomes; never synthesize successful results."""
import datetime,json,os,pathlib
STATUSES={'FINISHED','INTERRUPTED','RUNNING','WAITING','CREATED','UNKNOWN','HARNESS_ERROR','HARNESS_TIMEOUT'}
RESULTS={'PASSED','FAILED','WARNING','REVIEW','UNKNOWN'}
def document(run_id,started_at,plan_id,actual,requested):
    if not run_id or not plan_id or not requested:raise ValueError('missing provenance')
    dt=datetime.datetime.fromisoformat(started_at.replace('Z','+00:00'))
    if dt.tzinfo is None or dt>datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=10):raise ValueError('invalid start time')
    rows=[]
    for name in requested:
        matches=[a for a in actual if a.get('module')==name]
        if len(matches)!=1:raise ValueError('missing or duplicate requested module')
        a=matches[0]
        if not a.get('test_id'):raise ValueError('missing actual suite test ID')
        status=a.get('status');result=a.get('result')
        if status not in STATUSES or result not in RESULTS|{None}:raise ValueError('unrecognized suite status/result')
        rows.append({'module':name,'test_id':a['test_id'],'status':status,'result':result})
    return {'run':{'id':run_id,'started_at':started_at,'tool':'bounded-alpha-official-suite','evidence':'live official suite','plan_id':plan_id,'coverage':'selected modules only'},'certify':rows,'verify':[]}
def write(path,doc):
    p=pathlib.Path(path);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(doc,indent=2));os.replace(tmp,p)
def safe_conditions(entries):
    # Source class and verdict only. No args/msg/config/request/body fields.
    import re
    out=[]
    for e in entries:
        source=e.get('source');result=e.get('result')
        if isinstance(source,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,180}',source) and result in {'FAILURE','WARNING','SUCCESS','INFO'}:
            out.append({'source':source,'result':result})
    return out
