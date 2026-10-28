"""Audited synthetic-only handoffs. Unsupported modules always fail closed."""
import asyncio,importlib.util,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Handoffs:
 def __init__(self,args,configs):
  self.args=args;self.configs=configs;self.adapters={};self.driven={};self.review_config=None;self.window=getattr(args,'review_window',0) or 0
 def timeout_for(self,component):
  """Only the Verify review handoff gets the longer window; Certify never depends on review settings."""
  return self.window+180 if self.window and component=='verify' else None
 def _review(self):
  import os,time
  sys.path.insert(0,str(ROOT/'smoke/verify-final'));import review
  from conformance_runner import HarnessError
  try:
   if not getattr(self.args,'review_dir',None):raise review.ReviewError('review_configuration')
   review.need(0<self.window<=600,'review_configuration');run=os.environ.get('GITHUB_RUN_ID','');review.need(run,'review_configuration')
   return {'dir':self.args.review_dir,'window':self.window,'run_id':run,'source':review.github_source(),'clock':time.time,'sleep':asyncio.sleep,'interval':15}
  except review.ReviewError as e:raise HarnessError(str(e)) from None
 async def close(self):
  for adapter in self.adapters.values():
   if hasattr(adapter,'close'):await adapter.close()
 async def __call__(self,component,module,client):
  from conformance_runner import HarnessError
  try:
   if component=='verify':
    if 'verify' not in self.adapters:
     sys.path.insert(0,str(ROOT/'smoke/verify-final'));from adapter import Adapter
     self.review_config=self._review() if self.window else None;self.adapters['verify']=Adapter(self.args.ca_file,self.args.evidence_dir,self.args.base_url,self.review_config)
    await self.adapters['verify'](component,module,client);return
   if component=='certify':
    config=self.configs[component]
    if config.get('alias')!='alpha-official' or config.get('vci',{}).get('credential_issuer_url')!='https://certify.local.test:8443':raise HarnessError('issuer_handoff_configuration')
    if self.args.base_url!='https://suite:8443':raise HarnessError('issuer_handoff_suite')
    if 'certify' not in self.adapters:
     sys.path.insert(0,str(ROOT/'smoke/alpha-suite'));from official_driver import Driver
     self.adapters['certify']=Driver(self.args.ca_file,pathlib.Path(self.args.evidence_dir))
    driver=self.adapters['certify'];response=await asyncio.to_thread(driver.api,'GET','/api/runner/'+module);status=response.json()
    if status.get('id')!=module or status.get('name')!='oid4vci-1_0-issuer-happy-flow':raise HarnessError('issuer_handoff_unsupported_module')
    browser=status.get('browser',{});urls=browser.get('urls');seen=self.driven.setdefault(module,set())
    if not isinstance(urls,list):raise HarnessError('issuer_browser_shape')
    for url in urls:
     if not isinstance(url,str):raise HarnessError('issuer_browser_url')
     if url not in seen:
      seen.add(url);await asyncio.to_thread(driver.browser,url)
    return
   raise HarnessError('handoff_component')
  except HarnessError:raise
  except Exception:raise HarnessError('synthetic_handoff_failure') from None
