"""Pinned official automation library + bounded, fail-closed project orchestration.

No raw API config/log/error is written. A missing handoff remains a harness error,
never a product verdict. Existing environments require explicit JSON configuration.
Provisioned synthetic stacks use their own adapters and verified TLS CA.
"""
import argparse,asyncio,contextlib,datetime,hashlib,importlib.util,json,pathlib,re,sys,time,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
LIB=ROOT/'vendor/openid-suite/conformance.py'
SHA='660214cc6ca9b3c09297f61908a575db7b1552e8f44eecd5740d1c27fa2cfca8'
PLANS={'certify':'oid4vci-1_0-issuer-test-plan','verify':'oid4vp-1final-verifier-test-plan'}
STATES={'NOT_YET_CREATED','CREATED','CONFIGURED','RUNNING','WAITING','FINISHED','INTERRUPTED'}
RESULTS={'PASSED','FAILED','WARNING','REVIEW','SKIPPED','UNKNOWN',None}
class HarnessError(RuntimeError):pass
class Sink:
 def write(self,value):return len(value)
 def flush(self):pass

def official(base,ca):
 if hashlib.sha256(LIB.read_bytes()).hexdigest()!=SHA:raise HarnessError('official_library_integrity')
 spec=importlib.util.spec_from_file_location('pinned_conformance',LIB);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.Conformance(base,None,ca or True)

def check(ok,category):
 if not ok:raise HarnessError(category)
def identifier(value):
 check(isinstance(value,str) and re.fullmatch('[A-Za-z0-9]{8,32}',value),'suite_identifier');return value
def atomic(path,document):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(document,indent=2));tmp.replace(path)

class Runner:
 def __init__(self,client,timeout=300,handoff=None):self.client=client;self.timeout=timeout;self.handoff=handoff
 async def call(self,method,*args):
  # Upstream exceptions may contain config, token or error bodies. Never forward them.
  try:
   with contextlib.redirect_stdout(Sink()),contextlib.redirect_stderr(Sink()):return await asyncio.wait_for(method(*args),timeout=min(self.timeout,30))
  except Exception:raise HarnessError('suite_api_failure') from None
 async def run(self,component,configuration,variant,selected=None,checkpoint=None):
  plan=await self.call(self.client.create_test_plan,PLANS[component],json.dumps(configuration),variant)
  pid=identifier(plan.get('id'));check(plan.get('name')==PLANS[component],'created_plan_name')
  entries=plan.get('modules');check(isinstance(entries,list) and bool(entries),'empty_plan')
  names=[x.get('testModule') for x in entries if isinstance(x,dict)];check(len(names)==len(entries) and all(isinstance(x,str) for x in names),'module_list')
  check(len(names)==len(set(names)),'variant_expansion_requires_explicit_adapter');check(not selected or set(selected)<=set(names),'selected_modules_unknown')
  requested=selected or names;rows=[]
  for name in requested:
   module=await self.call(self.client.create_test_from_plan,pid,name);mid=identifier(module.get('id'));check(module.get('name')==name,'created_module_name')
   await self.call(self.client.start_test,mid)
   row={'module':name,'test_id':mid,'status':'HARNESS_TIMEOUT','result':None};deadline=time.monotonic()+self.timeout
   try:
    while time.monotonic()<deadline:
     info=await self.call(self.client.get_module_info,mid)
     check(info.get('testId')==mid and info.get('testName')==name and info.get('status') in STATES and info.get('result') in RESULTS,'module_info')
     status=info['status']
     if status in {'FINISHED','INTERRUPTED'}:row.update(status=status,result=info.get('result'));break
     if status=='WAITING':
      check(self.handoff is not None,'handoff_unavailable')
      try:await asyncio.wait_for(self.handoff(component,mid,self.client),timeout=min(self.timeout,60))
      except Exception:raise HarnessError('handoff_incomplete_or_failed') from None
     await asyncio.sleep(0.25)
   except HarnessError as e:row.update(status='HARNESS_ERROR',harness_category=str(e),result=None)
   rows.append(row)
   if checkpoint:checkpoint(rows)
  return {'plan_id':pid,'requested':requested,'coverage':'selected modules' if selected else 'created plan module names','rows':rows}

def gate(rows):return bool(rows) and all(x.get('status')=='FINISHED' and x.get('result')=='PASSED' for x in rows)
async def execute(args):
 output=pathlib.Path(args.output);output.unlink(missing_ok=True);output.with_suffix(output.suffix+'.tmp').unlink(missing_ok=True)
 doc={'run':{'id':args.run_id or str(uuid.uuid4()),'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool':'pinned official library + bounded project runner','evidence':'suite API responses from configured target; deployment provenance checked separately'},'plans':{}}
 client=official(args.base_url,args.ca_file);handoffs=None
 if args.synthetic_handoffs:
  check(args.ca_file and args.evidence_dir and args.base_url=='https://suite:8443','synthetic_handoff_scope')
  pathlib.Path(args.evidence_dir).mkdir(parents=True,exist_ok=True)
  from handoffs import Handoffs
  handoffs=Handoffs(args,{})
 try:
  for component in (['certify','verify'] if args.combined else [args.component]):
   config_file=getattr(args,component+'_config');check(config_file is not None,'explicit_configuration_required')
   configuration=json.loads(pathlib.Path(config_file).read_text(encoding='utf-8-sig'));variant=json.loads(pathlib.Path(getattr(args,component+'_variants')).read_text()) if getattr(args,component+'_variants') else {}
   def save(rows):doc[component]=rows;atomic(output,doc)
   if handoffs:handoffs.configs[component]=configuration
   result=await Runner(client,args.module_timeout,handoffs).run(component,configuration,variant,args.module,save)
   doc[component]=result.pop('rows');doc['plans'][component]=result;atomic(output,doc)
 finally:
  await client.close_client()
  if handoffs:await handoffs.close()
 return 0 if all(gate(doc.get(c,[])) for c in (['certify','verify'] if args.combined else [args.component])) else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--component',choices=PLANS);mode.add_argument('--combined',action='store_true')
 p.add_argument('--base-url',default='https://suite:8443');p.add_argument('--ca-file');p.add_argument('--output',default='conformance-results.json');p.add_argument('--run-id');p.add_argument('--synthetic-handoffs',action='store_true');p.add_argument('--evidence-dir');p.add_argument('--module-timeout',type=int,default=300);p.add_argument('--module',action='append')
 for c in PLANS:p.add_argument('--'+c+'-config');p.add_argument('--'+c+'-variants')
 args=p.parse_args()
 sys.modules['conformance_runner']=sys.modules[__name__]
 try:
  check(args.module_timeout>0,'timeout_positive')
  return asyncio.run(execute(args))
 except Exception as e:print('HARNESS_ERROR '+(str(e) if isinstance(e,HarnessError) else 'configuration_or_transport_failure'),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
