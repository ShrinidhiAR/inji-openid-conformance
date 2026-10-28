"""Bounded Final/DCQL backend bridge. Local implementation, runtime unverified.

Only audited happy-flow is supported initially; negative modules fail closed.
Evidence upload deliberately absent until actual product result pixels inspected.
An observed result is recorded separately, never promoted to official PASSED.
"""
import asyncio,json,pathlib,time,uuid,re,subprocess,shutil
from evidence import write as write_evidence
from contract import ContractError,require,request,wallet_query,handoff_url,result_projection,RESULT_REQUEST,SERVICE
class Adapter:
 def __init__(self,ca,output,suite='https://suite:8443'):
  import httpx
  require(suite=='https://suite:8443','suite_origin')
  self.http=httpx.AsyncClient(verify=ca,timeout=15,follow_redirects=False,trust_env=False);self.output=pathlib.Path(output);self.suite=suite;self.modules={}
 async def close(self):await self.http.aclose()
 async def exchange(self,method,url,status,**kwargs):
  try:
   response=await self.http.request(method,url,**kwargs)
   require(response.status_code in status,'bridge_http_status')
   require(len(response.content)<=2*1024*1024,'bridge_response_size')
   return response
  except ContractError:raise
  except Exception:raise ContractError('bridge_transport') from None
 async def __call__(self,component,module,client):
  require(component=='verify','bridge_component')
  require(isinstance(module,str) and re.fullmatch('[A-Za-z0-9]{8,32}',module),'bridge_module_identifier')
  # Officialclient is shared only for same-target status reads; do not trust
  # arbitrary exposed URLs or follow redirects to other hosts.
  response=await self.exchange('GET',self.suite+'/api/runner/'+module,{200});status=response.json()
  require(status.get('id')==module and status.get('name')=='oid4vp-1final-verifier-happy-flow','bridge_unsupported_module')
  state=self.modules.get(module)
  if state is None:
   inputs=status.get('browser',{}).get('uriInputRequests');require(isinstance(inputs,list) and len(inputs)==1,'wallet_input_request')
   transaction=str(uuid.uuid4());created=await self.exchange('POST',SERVICE+'/v2/vp-request',{201},json=request(transaction));details=created.json();query=wallet_query(details,transaction)
   url=handoff_url(inputs[0].get('submitUrl',''),self.suite,module,query)
   # Record before side effect to avoid duplicate fresh transaction on a retry.
   state={'transaction':transaction,'started':time.monotonic(),'submitted':False};self.modules[module]=state
   await self.exchange('GET',url,{200});state['submitted']=True
  require(state['submitted'],'wallet_handoff_incomplete')
  if state.get('projection'):raise ContractError('actual_result_evidence_requires_visual_review')
  # Result route performs full verification; 404 can mean submission not yet
  # stored, but all other non200 status stays a harness error, not productverdict.
  result=await self.exchange('POST',SERVICE+'/v2/vp-results/'+state['transaction'],{200,404},json=RESULT_REQUEST)
  if result.status_code==404:
   require(time.monotonic()-state['started']<30,'verification_result_missing');return
  projection=result_projection(result.json(),state['transaction']);projection['test_id']=module
  self.output.mkdir(parents=True,exist_ok=True);target=self.output/(module+'-verify-result.json');temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(projection,indent=2));temporary.replace(target);state['projection']=projection
  html=write_evidence(projection,self.output,module)
  await self.capture(html,module)
 async def capture(self,html,module):
  chrome=shutil.which('google-chrome') or shutil.which('chromium')
  require(chrome is not None,'result_screenshot_browser_missing')
  screenshot=self.output/(module+'-verify-result.png')
  rendered=await asyncio.to_thread(subprocess.run,[chrome,'--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1200,1000','--screenshot='+str(screenshot.resolve()),html.resolve().as_uri()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
  require(rendered.returncode==0 and screenshot.exists(),'result_screenshot_render_failure')
  # The official happyflow remains WAITING until its evidenceplaceholder has
  # genuinely been filled. Genericrunner must not synthesize terminalsuccess.
