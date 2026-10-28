"""Audited synthetic-only handoffs. Unsupported modules always fail closed."""
import asyncio,importlib.util,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Handoffs:
 def __init__(self,args,configs):
  self.args=args;self.configs=configs;self.adapters={};self.driven={}
 async def close(self):
  for adapter in self.adapters.values():
   if hasattr(adapter,'close'):await adapter.close()
 async def __call__(self,component,module,client):
  from conformance_runner import HarnessError
  try:
   if component=='verify':
    if 'verify' not in self.adapters:
     sys.path.insert(0,str(ROOT/'smoke/verify-final'));from adapter import Adapter
     self.adapters['verify']=Adapter(self.args.ca_file,self.args.evidence_dir,self.args.base_url)
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
