"""Run/test/hash-bound human review of the actual Verify result image before upload to the suite placeholder.
Never synthesizes a verdict: the suite itself ends the test as REVIEW when the placeholder is filled.
The image is a project-rendered view of the Verify v2 result API response, not the native Verify UI."""
import asyncio,base64,hashlib,json,os,pathlib,re,stat,struct,time,secrets
SCHEMA=1;MAX_PNG=400*1024
DESCRIPTION='Project-rendered view of the actual Verify v2 result API response. Not the native Verify UI. Not certification or trust.'
class ReviewError(ValueError):pass
def need(ok,category):
 if not ok:raise ReviewError(category)
def approval_path(run_id,test_id):return 'review-approvals/%s-%s.json'%(run_id,test_id)
def valid_ids(run_id,test_id):
 need(isinstance(run_id,str) and re.fullmatch('[A-Za-z0-9-]{1,64}',run_id),'review_configuration');need(isinstance(test_id,str) and re.fullmatch('[A-Za-z0-9]{8,32}',test_id),'review_configuration')
def make_manifest(run_id,test_id,placeholder,png,window,now,projection=b'',html=b''):
 valid_ids(run_id,test_id);need(isinstance(placeholder,str) and re.fullmatch('[A-Za-z0-9_-]{6,64}',placeholder),'review_placeholder_missing')
 need(png[:8]==b'\x89PNG\r\n\x1a\n' and 0<len(png)<=MAX_PNG,'review_image_invalid');need(isinstance(window,int) and 0<window<=600,'review_configuration')
 return {'schema':SCHEMA,'run_id':run_id,'test_id':test_id,'placeholder':placeholder,'png_sha256':hashlib.sha256(png).hexdigest(),'png_bytes':len(png),'projection_sha256':hashlib.sha256(projection).hexdigest(),'html_sha256':hashlib.sha256(html).hexdigest(),'created_at':int(now),'deadline':int(now)+window,'description':DESCRIPTION,'approval_path':approval_path(run_id,test_id)}
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

MANIFEST_KEYS={'schema','run_id','test_id','placeholder','png_sha256','png_bytes','projection_sha256','html_sha256','created_at','deadline','description','approval_path'}
PROJECTION_KEYS={'transaction_matches','credential_count','all_checks_successful','checks','source','test_id'}
CHECK_KEYS={'schemaAndSignatureCheck','expiryCheck','holderProofCheck','status_checks_returned','status_checks_valid','all_checks_successful'}
def check_request(directory,evidence,run_id,now):
  """Gate before the early public artifact: parsed manifest fields, files, and provenance of the image."""
  import struct
  d=pathlib.Path(directory);e=pathlib.Path(evidence)
  names=sorted(x.name for x in d.iterdir());need('manifest.json' in names,'review_artifact_invalid')
  need(not any(x.is_symlink() for x in d.iterdir()),'review_artifact_invalid')
  m=json.loads((d/'manifest.json').read_text());need(isinstance(m,dict) and set(m)==MANIFEST_KEYS,'review_artifact_invalid')
  test=m['test_id'];valid_ids(m['run_id'],test);need(m['run_id']==run_id and m['schema']==SCHEMA,'review_artifact_invalid')
  need(names==sorted(['manifest.json',test+'-verify-result.png']),'review_artifact_invalid')
  need(isinstance(m['placeholder'],str) and re.fullmatch('[A-Za-z0-9_-]{6,64}',m['placeholder']),'review_artifact_invalid')
  need(m['description']==DESCRIPTION and m['approval_path']==approval_path(run_id,test),'review_artifact_invalid')
  need(all(isinstance(m[k],int) and not isinstance(m[k],bool) for k in ('created_at','deadline','png_bytes')) and 0<m['deadline']-m['created_at']<=600,'review_artifact_invalid')
  need(int(now)<=m['deadline'],'review_window_expired')
  png=(d/(test+'-verify-result.png')).read_bytes();need(hashlib.sha256(png).hexdigest()==m['png_sha256'] and len(png)==m['png_bytes']<=MAX_PNG and png[:8]==b'\x89PNG\r\n\x1a\n','review_artifact_invalid')
  w,h=struct.unpack('>II',png[16:24]);need(png[12:16]==b'IHDR' and 0<w<=4000 and 0<h<=4000,'review_artifact_invalid')
  proj=(e/(test+'-verify-result.json')).read_bytes();html=(e/(test+'-verify-result.html')).read_bytes()
  need(hashlib.sha256(proj).hexdigest()==m['projection_sha256'] and hashlib.sha256(html).hexdigest()==m['html_sha256'],'review_artifact_invalid')
  doc=json.loads(proj);need(isinstance(doc,dict) and set(doc)==PROJECTION_KEYS and doc['test_id']==test and doc['source']=='Verify v2 result API projection','review_artifact_invalid')
  need(isinstance(doc['checks'],list) and all(isinstance(c,dict) and set(c)==CHECK_KEYS for c in doc['checks']),'review_artifact_invalid')
  need(b'<script' not in html.lower() and b'http://' not in html and b'https://' not in html,'review_artifact_invalid')

# ---- Local approval source (no GitHub, no token): a private directory on this machine, same validate() as every other source ----
APPROVAL_NAME='review-approvals/[A-Za-z0-9-]+-[A-Za-z0-9]+\\.json'
def private_dir(path):
 """A real directory (never a symlink) owned by this user that nobody else can write to."""
 try:st=os.lstat(path)
 except OSError:raise ReviewError('review_configuration') from None
 need(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o022,'review_configuration')
 return str(path)
def read_private_file(directory,name,limit,category):
 """Open without following symlinks; regular file, same owner, not group/other writable, bounded size. None when absent."""
 need(re.fullmatch('[A-Za-z0-9._-]+',name) and not name.startswith('.'),category)
 try:fd=os.open(os.path.join(private_dir(directory),name),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 except FileNotFoundError:return None
 except OSError:raise ReviewError(category) from None
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o022 and st.st_size<=limit,category)
  return os.read(fd,limit+1)
 finally:os.close(fd)
def local_source(directory):
 private_dir(directory)
 async def fetch(path):
  need(isinstance(path,str) and re.fullmatch(APPROVAL_NAME,path),'review_configuration')
  data=read_private_file(directory,path.split('/',1)[1],4096,'approval_invalid')
  if data is None:return None
  try:return json.loads(data)
  except Exception:raise ReviewError('approval_invalid') from None
 return fetch
def read_request(request_dir,now):
  """Parsed and checked review request from a private local directory: manifest fields, window, image bytes and hash."""
  raw=read_private_file(request_dir,'manifest.json',8192,'review_artifact_invalid');need(raw is not None,'review_artifact_invalid')
  try:m=json.loads(raw)
  except Exception:raise ReviewError('review_artifact_invalid') from None
  need(isinstance(m,dict) and set(m)==MANIFEST_KEYS and m['schema']==SCHEMA,'review_artifact_invalid')
  valid_ids(m['run_id'],m['test_id']);need(m['description']==DESCRIPTION and m['approval_path']==approval_path(m['run_id'],m['test_id']),'review_artifact_invalid')
  need(all(isinstance(m[k],int) and not isinstance(m[k],bool) for k in ('created_at','deadline','png_bytes')) and 0<m['deadline']-m['created_at']<=600,'review_artifact_invalid')
  need(int(now)<=m['deadline'],'review_window_expired')
  png=read_private_file(request_dir,m['test_id']+'-verify-result.png',MAX_PNG,'review_artifact_invalid');need(png is not None,'review_artifact_invalid')
  need(png[:8]==b'\x89PNG\r\n\x1a\n' and len(png)==m['png_bytes'] and hashlib.sha256(png).hexdigest()==m['png_sha256'],'review_artifact_invalid')
  need(png[12:16]==b'IHDR','review_artifact_invalid');w,h=struct.unpack('>II',png[16:24]);need(0<w<=4000 and 0<h<=4000,'review_artifact_invalid')
  return m,png,(w,h)
def write_local_approval(request_dir,approvals_dir,typed_hash,now):
  """Write the hash-bound approval only when the typed sha256 equals the sha256 of the image bytes in the request. Never overwrites."""
  m,png,_=read_request(request_dir,now);private_dir(approvals_dir)
  typed=typed_hash.strip().lower() if isinstance(typed_hash,str) else '';need(re.fullmatch('[0-9a-f]{64}',typed) and typed==hashlib.sha256(png).hexdigest()==m['png_sha256'],'approval_mismatch')
  record={'schema':SCHEMA,'run_id':m['run_id'],'test_id':m['test_id'],'png_sha256':typed,'approved_at':int(now),'decision':'approve_faithful_view'};validate(record,m,png,now)
  target=os.path.join(approvals_dir,m['approval_path'].split('/',1)[1]);temp=os.path.join(approvals_dir,'.tmp-'+secrets.token_hex(8))
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  try:
   with os.fdopen(fd,'w') as f:f.write(json.dumps(record,indent=1)+'\n');f.flush();os.fsync(f.fileno())
   try:os.link(temp,target)   # atomic and refuses an existing approval
   except FileExistsError:raise ReviewError('approval_invalid') from None
  finally:os.unlink(temp)
  return target
