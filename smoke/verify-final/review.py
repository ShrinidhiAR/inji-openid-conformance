"""Run/test/hash-bound human review of the actual Verify result image before upload to the suite placeholder.
Never synthesizes a verdict: the suite itself ends the test as REVIEW when the placeholder is filled.
The image is a project-rendered view of the Verify v2 result API response, not the native Verify UI."""
import asyncio,base64,hashlib,json,os,pathlib,re,time
SCHEMA=1;MAX_PNG=400*1024
DESCRIPTION='Project-rendered view of the actual Verify v2 result API response. Not the native Verify UI. Not certification or trust.'
class ReviewError(ValueError):pass
def need(ok,category):
 if not ok:raise ReviewError(category)
def approval_path(run_id,test_id):return 'review-approvals/%s-%s.json'%(run_id,test_id)
def valid_ids(run_id,test_id):
 need(isinstance(run_id,str) and re.fullmatch('[A-Za-z0-9-]{1,64}',run_id),'review_configuration');need(isinstance(test_id,str) and re.fullmatch('[A-Za-z0-9]{8,32}',test_id),'review_configuration')
def make_manifest(run_id,test_id,placeholder,png,window,now):
 valid_ids(run_id,test_id);need(isinstance(placeholder,str) and re.fullmatch('[A-Za-z0-9_-]{6,64}',placeholder),'review_placeholder_missing')
 need(png[:8]==b'\x89PNG\r\n\x1a\n' and 0<len(png)<=MAX_PNG,'review_image_invalid');need(isinstance(window,int) and 0<window<=600,'review_configuration')
 return {'schema':SCHEMA,'run_id':run_id,'test_id':test_id,'placeholder':placeholder,'png_sha256':hashlib.sha256(png).hexdigest(),'png_bytes':len(png),'created_at':int(now),'deadline':int(now)+window,'description':DESCRIPTION,'approval_path':approval_path(run_id,test_id)}
APPROVAL_KEYS={'schema','run_id','test_id','png_sha256','approved_at','decision'}
def validate(approval,manifest,png,now):
 need(isinstance(approval,dict) and set(approval)==APPROVAL_KEYS,'approval_invalid')
 need(approval['schema']==SCHEMA and approval['decision']=='approve_faithful_view','approval_invalid')
 need(approval['run_id']==manifest['run_id'] and approval['test_id']==manifest['test_id'],'approval_mismatch')
 digest=hashlib.sha256(png).hexdigest();need(approval['png_sha256']==manifest['png_sha256']==digest,'approval_mismatch')
 at=approval['approved_at'];need(isinstance(at,int) and not isinstance(at,bool),'approval_invalid')
 need(at>=manifest['created_at'],'approval_stale');need(at<=int(now)+60,'approval_invalid');need(int(now)<=manifest['deadline'],'review_window_expired')
async def wait_for_approval(source,manifest,png,clock=time.time,sleep=asyncio.sleep,interval=15):
 while True:
  now=clock();need(now<=manifest['deadline'],'review_window_expired')
  record=await source(manifest['approval_path'])
  if record is not None:validate(record,manifest,png,clock());return
  await sleep(interval)
def github_source(env=os.environ,client=None):
 """Read-only poll of a run-specific path on the already-existing branch with the job's own contents:read token."""
 import httpx
 repo=env.get('GITHUB_REPOSITORY','');token=env.get('GITHUB_TOKEN','');branch=env.get('GITHUB_REF_NAME','')
 need(re.fullmatch('[A-Za-z0-9._-]+/[A-Za-z0-9._-]+',repo) and token and branch=='e2e-full-run','review_configuration')
 async def fetch(path):
  need(re.fullmatch('review-approvals/[A-Za-z0-9-]+-[A-Za-z0-9]+\\.json',path),'review_configuration')
  c=client or httpx.AsyncClient(timeout=15,follow_redirects=False,trust_env=False)
  try:
   r=await c.get('https://api.github.com/repos/%s/contents/%s'%(repo,path),params={'ref':branch},headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github.raw+json','X-GitHub-Api-Version':'2022-11-28'})
  except Exception:raise ReviewError('approval_transport') from None
  finally:
   if client is None:await c.aclose()
  if r.status_code==404:return None
  need(r.status_code==200 and len(r.content)<=4096,'approval_transport')
  try:return json.loads(r.content)
  except Exception:raise ReviewError('approval_invalid') from None
 return fetch
def data_uri(png):return 'data:image/png;base64,'+base64.b64encode(png).decode()
def write_request(directory,manifest,png,module):
 d=pathlib.Path(directory);d.mkdir(parents=True,exist_ok=True)
 (d/(module+'-verify-result.png')).write_bytes(png)
 t=d/'manifest.json.tmp';t.write_text(json.dumps(manifest,indent=2));t.replace(d/'manifest.json')  # manifest last: it is the ready signal
