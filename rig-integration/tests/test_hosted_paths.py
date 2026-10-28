"""Hosted-runner path contract: real stage_isolated.py (real clone of the pinned upstream), real fallback_cleanup.py path guards,
real run_combined output guard, real script work-dir guard. Only heavy external commands (mvn, docker, sudo) are stubbed.
RUNNER_TEMP is set like a hosted runner and must be irrelevant; work dir is /tmp/conformance-work-style."""
import json,os,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];S=str(ROOT/'run-full-stack-conformance.sh')
PIN='8fdf71656979a72fa8263766d4dec3cc25127b76'
HOSTED={'RUNNER_TEMP':'/home/runner/work/_temp'}
MVN='#!/bin/bash\necho "mvn $*" >> "$SHIM_LOG"\nout=""\nfor a in "$@"; do case "$a" in -Dmdep.outputFile=*) out="${a#*=}";; esac; done\n[ -z "$out" ] || echo deps.jar > "$out"\nexit 0\n'
def clone(dest):
 try:
  subprocess.run(['git','clone','--no-checkout','-q','https://github.com/inji/inji-certify',str(dest)],check=True,timeout=120,capture_output=True)
  subprocess.run(['git','-C',str(dest),'checkout','-q','--detach',PIN],check=True,timeout=120,capture_output=True)
  return True
 except Exception:return False
class Hosted(unittest.TestCase):
 def setUp(self):
  self.work=pathlib.Path(tempfile.mkdtemp(prefix='conformance-work-',dir='/tmp'));self.addCleanup(shutil.rmtree,self.work,True)
  self.bin=self.work.parent/(self.work.name+'-bin');self.bin.mkdir();self.addCleanup(shutil.rmtree,self.bin,True)
  (self.bin/'mvn').write_text(MVN);(self.bin/'mvn').chmod(0o755)
  self.log=self.bin/'log'
 def env(self,**k):
  e=dict(os.environ);e.update(HOSTED);e.update(PATH=str(self.bin)+':'+os.environ['PATH'],SHIM_LOG=str(self.log),JAVA_HOME='/jdk',CONFORMANCE_WORK=str(self.work));e.pop('TMPDIR',None);e.update(k);return e
 def test_real_staging_accepts_hosted_work_dir_and_feeds_mvn(self):
  up=self.work/'native-certify-upstream'
  if not clone(up):self.skipTest('upstream clone unavailable (no network)')
  r=subprocess.run(['python3',str(ROOT/'rig-integration/stage_isolated.py'),'--component','certify','--upstream',str(up),'--destination',str(self.work/'native-certify-rig')],capture_output=True,text=True,env=self.env())
  self.assertEqual(r.returncode,0,r.stderr);self.assertTrue((self.work/'native-certify-rig/pom.xml').is_file())
 def test_script_prepare_reaches_mvn_with_absolute_paths_then_stops_at_minio(self):
  if not clone(self.work/'native-certify-upstream'):self.skipTest('upstream clone unavailable (no network)')
  # go is hidden so the MinIO build fails closed right after the staging/compile contract has been exercised
  e=self.env(PATH=str(self.bin)+':/usr/bin:/bin')
  r=subprocess.run(['bash',S,'--component','certify','--approve-runtime','--phase','prepare','--output',str(self.work/'out')],capture_output=True,text=True,env=e,timeout=300)
  log=self.log.read_text()
  self.assertIn('-f '+str(self.work/'native-certify-rig/pom.xml'),log);self.assertIn('-Dmdep.outputFile='+str(self.work/'native-certify-classpath'),log)
  self.assertTrue((self.work/'native-certify-rig/pom.xml').is_file());self.assertNotIn('new_temporary_destination_required',r.stderr)
 def locator(self,private,out):
  o=self.work/'owned';o.mkdir();(o/'hosts.backup').write_text('127.0.0.1 localhost\n')
  loc=o/'locator.json';loc.write_text(json.dumps({'project':'conformance-0123456789ab','private':str(private),'compose':str(private/'compose.yml'),'hosts_backup':str(o/'hosts.backup'),'output':str(out),'process_groups':[]}));return loc
 def test_fallback_cleanup_accepts_hosted_layout_and_refuses_runner_temp_private(self):
  private=pathlib.Path(tempfile.mkdtemp(prefix='alpha-private-',dir='/tmp'));self.addCleanup(shutil.rmtree,private,True);out=self.work/'out';out.mkdir()
  r=subprocess.run(['python3',str(ROOT/'rig-integration/fallback_cleanup.py'),'--locator',str(self.locator(private,out))],capture_output=True,text=True,env=self.env())
  self.assertNotIn('fallback_private_path_scope',r.stderr);self.assertNotIn('fallback_project_scope',r.stderr);self.assertTrue((out/'cleanup.json').exists())
 def test_fallback_cleanup_refuses_private_under_runner_temp(self):
  out=self.work/'out';out.mkdir()
  r=subprocess.run(['python3',str(ROOT/'rig-integration/fallback_cleanup.py'),'--locator',str(self.locator(pathlib.Path('/home/runner/work/_temp/alpha-private-x'),out))],capture_output=True,text=True,env=self.env())
  self.assertNotEqual(r.returncode,0);self.assertIn('fallback_private_path_scope',r.stderr)
 def test_script_refuses_runner_temp_work_dir(self):
  r=subprocess.run(['bash',S,'--component','certify','--approve-runtime'],capture_output=True,text=True,env=self.env(CONFORMANCE_WORK='/home/runner/work/_temp/conformance-work'))
  self.assertEqual(r.returncode,2);self.assertIn('under /tmp',r.stderr)
 def test_script_refuses_when_system_temp_is_not_tmp(self):
  r=subprocess.run(['bash',S,'--component','certify','--approve-runtime'],capture_output=True,text=True,env=self.env(TMPDIR='/home/runner/work/_temp'))
  self.assertEqual(r.returncode,2);self.assertIn('TMPDIR',r.stderr)
 def test_run_combined_refuses_existing_output(self):
  out=self.work/'out';out.mkdir()
  r=subprocess.run(['python3',str(ROOT/'rig-integration/run_combined.py'),'--output',str(out),'--locator',str(self.work/'owned/locator.json'),'--java-home','/jdk','--minio-binary','/x','--minio-provenance','/x.json','--component','certify','--certify-classpath','a'],capture_output=True,text=True,env=self.env())
  self.assertNotEqual(r.returncode,0);self.assertIn('fresh_evidence_directory_required',r.stderr+r.stdout)
if __name__=='__main__':unittest.main()
