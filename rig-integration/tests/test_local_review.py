"""Local review option: private approval directory, second-terminal helper, script wiring. Real validator, mock suite, no network, no GitHub.
Not runtime evidence: nothing here boots the stack."""
import asyncio,hashlib,io,json,os,pathlib,subprocess,sys,tempfile,unittest
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
for p in (ROOT/'smoke/verify-final',ROOT/'scripts',ROOT/'rig-integration',HERE):sys.path.insert(0,str(p))
import review,review_local,handoffs
from conformance_runner import HarnessError  # noqa
import test_entrypoint as te
PNG=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(1200).to_bytes(4,'big')+(900).to_bytes(4,'big')+b'\x08\x02\x00\x00\x00'+b'x'*50
RUN='combined-0123456789abcdef-verify';TEST='module12345678';NOW=100_000
def setup(now=NOW,window=600,png=PNG):
 w=pathlib.Path(tempfile.mkdtemp(dir='/tmp'));req=w/'review-request';ap=w/'review-approvals'
 req.mkdir(mode=0o700);ap.mkdir(mode=0o700);os.chmod(req,0o700);os.chmod(ap,0o700)
 m=review.make_manifest(RUN,TEST,'ph_abcdef',png,window,now);review.write_request(req,m,png,TEST);return w,req,ap,m
def sha(b):return hashlib.sha256(b).hexdigest()
def valid(m,**kw):
 r={'schema':1,'run_id':m['run_id'],'test_id':m['test_id'],'png_sha256':m['png_sha256'],'approved_at':m['created_at']+5,'decision':'approve_faithful_view'};r.update(kw);return r
def fetch(src,path='review-approvals/%s-%s.json'%(RUN,TEST)):return asyncio.run(src(path))
class Source(unittest.TestCase):
 def test_missing_is_none_and_valid_is_returned(self):
  w,req,ap,m=setup();src=review.local_source(ap);self.assertIsNone(fetch(src))
  (ap/(RUN+'-'+TEST+'.json')).write_text(json.dumps(valid(m)));os.chmod(ap/(RUN+'-'+TEST+'.json'),0o600);self.assertEqual(fetch(src)['decision'],'approve_faithful_view')
 def test_bad_paths_rejected(self):
  w,req,ap,m=setup();src=review.local_source(ap)
  for p in ('review-approvals/../x.json','review-approvals/a/b.json','/etc/passwd','review-approvals/'+RUN+'-'+TEST+'.json/','x.json','review-approvals/.hidden-abcdefgh.json',None):
   with self.assertRaises(review.ReviewError,msg=p):fetch(src,p)
 def test_symlink_file_dir_nonregular_oversize_loose_and_bad_json(self):
  w,req,ap,m=setup();src=review.local_source(ap);f=ap/(RUN+'-'+TEST+'.json');t=w/'real.json';t.write_text(json.dumps(valid(m)))
  f.symlink_to(t)
  with self.assertRaises(review.ReviewError):fetch(src)
  f.unlink();os.mkfifo(f)
  with self.assertRaises(review.ReviewError):fetch(src)
  f.unlink();f.write_text(' '*5000);os.chmod(f,0o600)
  with self.assertRaises(review.ReviewError):fetch(src)
  f.write_text('{not json');os.chmod(f,0o600)
  with self.assertRaises(review.ReviewError):fetch(src)
  f.write_text(json.dumps(valid(m)));os.chmod(f,0o666)
  with self.assertRaises(review.ReviewError):fetch(src)
  os.chmod(f,0o600);os.chmod(ap,0o770)
  with self.assertRaises(review.ReviewError):fetch(src)
  with self.assertRaises(review.ReviewError):review.local_source(ap)
  os.chmod(ap,0o700);link=w/'lnk';link.symlink_to(ap)
  with self.assertRaises(review.ReviewError):review.local_source(link)
class Waiting(unittest.TestCase):
 def run_wait(self,record,now_at=NOW+10,window=600):
  w,req,ap,m=setup(window=window)
  if record is not None:
   f=ap/(RUN+'-'+TEST+'.json');f.write_text(json.dumps(record(m)));os.chmod(f,0o600)
  clock=[now_at]
  async def sleep(s):clock[0]+=s
  return asyncio.run(review.wait_for_approval(review.local_source(ap),m,PNG,lambda:clock[0],sleep,5))
 def test_accepted(self):self.run_wait(lambda m:valid(m))   # returns without raising
 def test_rejections(self):
  for name,rec in (('hash',lambda m:valid(m,png_sha256='0'*64)),('run',lambda m:valid(m,run_id='other-run')),('test',lambda m:valid(m,test_id='othermodule99')),('stale',lambda m:valid(m,approved_at=NOW-1)),('future',lambda m:valid(m,approved_at=NOW+9999)),('late',lambda m:valid(m,approved_at=NOW+601)),('extra',lambda m:dict(valid(m),note='x')),('decision',lambda m:valid(m,decision='yes'))):
   with self.assertRaises(review.ReviewError,msg=name):self.run_wait(rec)
 def test_no_approval_times_out(self):
  with self.assertRaises(review.ReviewError):self.run_wait(None,window=30)
class Helper(unittest.TestCase):
 def approve(self,w,h,now=NOW+5):
  err=io.StringIO();old=sys.stderr;sys.stderr=err
  try:rc=review_local.approve(type('A',(),{'work':str(w),'png_sha256':h})(),clock=lambda:now,out=lambda s:None)
  finally:sys.stderr=old
  return rc,err.getvalue()
 def test_exact_hash_only_mode_atomic_no_overwrite_and_validates(self):
  w,req,ap,m=setup()
  for bad in ('0'*64,'',sha(PNG)[:-1],sha(PNG)+'0','zz'):
   rc,e=self.approve(w,bad);self.assertEqual(rc,1,bad);self.assertEqual(os.listdir(ap),[])
  rc,e=self.approve(w,sha(PNG).upper());self.assertEqual(rc,0)
  f=ap/(RUN+'-'+TEST+'.json');self.assertEqual(os.listdir(ap),[f.name]);self.assertEqual(oct(os.stat(f).st_mode&0o777),'0o600')
  review.validate(json.loads(f.read_text()),m,PNG,NOW+5);self.assertEqual(json.loads(f.read_text())['approved_at'],NOW+5)
  rc,e=self.approve(w,sha(PNG));self.assertEqual(rc,1);self.assertEqual(os.listdir(ap),[f.name])
 def test_expired_rejected(self):
  w,req,ap,m=setup();rc,e=self.approve(w,sha(PNG),now=NOW+601);self.assertEqual(rc,1);self.assertEqual(os.listdir(ap),[])
 def test_png_changed_after_request_is_not_approvable(self):
  w,req,ap,m=setup();png=req/(TEST+'-verify-result.png');png.write_bytes(PNG+b'z');rc,e=self.approve(w,sha(PNG+b'z'));self.assertEqual(rc,1);self.assertEqual(os.listdir(ap),[])
 def test_symlinked_png_manifest_and_dirs_rejected(self):
  for what in ('png','manifest','req','ap'):
   w,req,ap,m=setup();o=w/'other';o.mkdir(mode=0o700)
   if what=='png':
    t=o/'p.png';t.write_bytes(PNG);(req/(TEST+'-verify-result.png')).unlink();(req/(TEST+'-verify-result.png')).symlink_to(t)
   if what=='manifest':
    t=o/'m.json';t.write_text((req/'manifest.json').read_text());(req/'manifest.json').unlink();(req/'manifest.json').symlink_to(t)
   if what=='req':os.rename(req,o/'r');req.symlink_to(o/'r')
   if what=='ap':os.rmdir(ap);ap.symlink_to(o)
   rc,e=self.approve(w,sha(PNG));self.assertEqual(rc,1,what);self.assertEqual(os.listdir(o) if what=='ap' else [],[] if what=='ap' else [])
 def test_loose_permission_dirs_rejected(self):
  for what in ('req','ap'):
   w,req,ap,m=setup();os.chmod(req if what=='req' else ap,0o775);rc,e=self.approve(w,sha(PNG));self.assertEqual(rc,1,what);self.assertEqual(os.listdir(ap),[])
 def test_show_prints_path_and_never_the_hash_or_a_credential(self):
  w,req,ap,m=setup();out=[]
  rc=review_local.show(type('A',(),{'work':str(w),'wait':1})(),clock=lambda:NOW+3,sleep=lambda s:None,out=out.append);t='\n'.join(out)
  self.assertEqual(rc,0);self.assertIn(TEST+'-verify-result.png',t);self.assertIn('sha256sum',t);self.assertNotIn(sha(PNG),t);self.assertNotIn('token',t.lower());self.assertIn('not the native Verify UI',t)
 def test_show_without_request_fails_and_after_deadline_fails(self):
  w=pathlib.Path(tempfile.mkdtemp(dir='/tmp'));(w/'review-request').mkdir(mode=0o700);t=[0]
  def clock():t[0]+=50;return t[0]
  self.assertEqual(review_local.show(type('A',(),{'work':str(w),'wait':60})(),clock=clock,sleep=lambda s:None,out=lambda s:None),1)
  w,req,ap,m=setup();self.assertEqual(review_local.show(type('A',(),{'work':str(w),'wait':1})(),clock=lambda:NOW+601,sleep=lambda s:None,out=lambda s:None),1)
class Args:pass
class HandoffConfig(unittest.TestCase):
 def cfg(self,env,run=RUN,w=None):
  w=w or setup()[0];a=Args();a.review_window=300;a.review_dir=str(w/'review-request');a.run_id=run;a.ca_file=None;a.evidence_dir=str(w/'ev');a.base_url='https://v'
  old=dict(os.environ)
  for k in list(os.environ):
   if k.startswith(('GITHUB_','CONFORMANCE_')):del os.environ[k]
  os.environ.update(env(w))
  try:return handoffs.Handoffs(a,{})._review()
  finally:os.environ.clear();os.environ.update(old)
 def test_local_needs_no_github_and_uses_own_run_id(self):
  c=self.cfg(lambda w:{'CONFORMANCE_REVIEW_SOURCE':'local','CONFORMANCE_REVIEW_APPROVALS_DIR':str(w/'review-approvals')});self.assertEqual(c['run_id'],RUN);self.assertEqual(c['window'],300);self.assertTrue(callable(c['source']))
 def test_local_ignores_github_run_id_and_rejects_bad_config(self):
  c=self.cfg(lambda w:{'CONFORMANCE_REVIEW_SOURCE':'local','CONFORMANCE_REVIEW_APPROVALS_DIR':str(w/'review-approvals'),'GITHUB_RUN_ID':'999','GITHUB_TOKEN':'x'});self.assertEqual(c['run_id'],RUN)
  with self.assertRaises(HarnessError):self.cfg(lambda w:{'CONFORMANCE_REVIEW_SOURCE':'local'})
  with self.assertRaises(HarnessError):self.cfg(lambda w:{'CONFORMANCE_REVIEW_SOURCE':'local','CONFORMANCE_REVIEW_APPROVALS_DIR':str(w/'review-approvals')},run='bad run!')
  with self.assertRaises(HarnessError):self.cfg(lambda w:{'CONFORMANCE_REVIEW_SOURCE':'local','CONFORMANCE_REVIEW_APPROVALS_DIR':str(w/'nope')})
 def test_github_path_unchanged_still_requires_its_variables(self):
  with self.assertRaises(Exception):self.cfg(lambda w:{})
class Script(unittest.TestCase):
 def envs(self,l):return pathlib.Path(str(l)+'.env').read_text().splitlines()
 def test_local_review_needs_work_dir_and_verify(self):
  r,l=te.sh('--combined','--review','local','--approve-runtime',work=False);self.assertEqual(r.returncode,2);self.assertEqual(l,[])
  r,l=te.sh('--component','certify','--review','local','--approve-runtime');self.assertEqual(r.returncode,2);self.assertEqual(l,[])
  for bad in (['--review'],['--review','github'],['--review','local','--review']):
   r,l=te.sh('--combined',*bad,'--approve-runtime');self.assertEqual(r.returncode,2,bad)
 def test_env_reaches_run_only_private_dirs_no_token(self):
  r,l=te.sh('--combined','--review','local','--approve-runtime',env={'GITHUB_TOKEN':'tok-secret','CONFORMANCE_REVIEW_WINDOW':''});self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn('review_local.py show --work',r.stderr);self.assertNotIn('tok-secret',r.stdout+r.stderr)
  run=[x for x in te.has(l,'run_combined.py')];self.assertEqual(len(run),1)
 def test_dirs_private_and_env_values(self):
  d=tempfile.mkdtemp(dir='/tmp');w=pathlib.Path(d)/'work'
  r,l=te.sh('--combined','--review','local','--approve-runtime',env={'CONFORMANCE_WORK':str(w),'GITHUB_TOKEN':'tok-secret'},work=False)
  self.assertEqual(r.returncode,0,r.stderr)
  for n in ('review-request','review-approvals'):self.assertEqual(oct(os.stat(w/n).st_mode&0o777),'0o700')
 def test_run_phase_env_and_prepare_isolation(self):
  r,l=te.sh('--combined','--review','local','--approve-runtime',env={'GITHUB_TOKEN':'tok-secret'});self.assertEqual(r.returncode,0,r.stderr)
  logs=[p for p in pathlib.Path(tempfile.gettempdir()).glob('tmp*/log.env')]
  mine=max(logs,key=lambda p:p.stat().st_mtime).read_text().splitlines()
  i=[n for n,x in enumerate(mine) if 'src=local' in x][0];prep=mine[:i];run=[mine[i]]
  self.assertEqual(len(run),1);self.assertIn('token=unset',run[0]);self.assertIn('window=600',run[0]);self.assertIn('review-request',run[0]);self.assertIn('review-approvals',run[0])
  for x in prep:self.assertIn('src=unset',x);self.assertIn('appr=unset',x);self.assertIn('token=unset',x)
 def test_stale_review_dir_refused(self):
  d=tempfile.mkdtemp(dir='/tmp');w=pathlib.Path(d)/'work';(w/'review-approvals').mkdir(parents=True)
  r,l=te.sh('--combined','--review','local','--approve-runtime',env={'CONFORMANCE_WORK':str(w)},work=False);self.assertNotEqual(r.returncode,0);self.assertEqual(te.has(l,'run_combined.py'),[]);self.assertIn('fresh CONFORMANCE_WORK',r.stderr)
if __name__=='__main__':unittest.main()
