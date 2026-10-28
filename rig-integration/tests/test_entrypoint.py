"""run-full-stack-conformance.sh routing, argv, cleanup and fail-closed behaviour, with every external command shimmed (nothing real runs)."""
import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];S=str(ROOT/'run-full-stack-conformance.sh')
SHIM='''#!/bin/bash
echo "$(basename $0) $*" >> "$SHIM_LOG"
case "$(basename $0) $*" in
 *run_combined.py*) if [ -n "$SHIM_HANG" ]; then trap 'echo run_combined_got_TERM >> "$SHIM_LOG"; kill $sp 2>/dev/null; exit 143' TERM; sleep 30 & sp=$!; wait $sp; fi; exit ${SHIM_RUN_EXIT:-0};;
 *audit_evidence.py*) exit ${SHIM_AUDIT_EXIT:-0};;
 *fallback_cleanup.py*) exit ${SHIM_CLEANUP_EXIT:-0};;
 *minio_native_acceptance.py*) exit ${SHIM_ACCEPT_EXIT:-0};;
esac
exit 0
'''
def sh(*a,env=None,work=True,run_exit=0,audit_exit=0,locator=True,out_exists=True,popen=False):
 d=tempfile.mkdtemp();b=pathlib.Path(d)/'bin';b.mkdir();log=pathlib.Path(d)/'log'
 for n in ('python3','git','mvn'):
  f=b/n;f.write_text(SHIM);f.chmod(0o755)
 w=pathlib.Path(d)/'work'
 for c in ('certify','verify'):
  w.mkdir(exist_ok=True);(w/('native-'+c+'-classpath')).write_text('deps-'+c+'.jar')
 if locator:(w/'owned').mkdir(exist_ok=True);(w/'owned/locator.json').write_text('{}')
 e={'PATH':str(b)+':/usr/bin:/bin','SHIM_LOG':str(log),'JAVA_HOME':'/jdk','SHIM_RUN_EXIT':str(run_exit),'SHIM_AUDIT_EXIT':str(audit_exit),'SHIM_HANG':''}
 if work:e['CONFORMANCE_WORK']=str(w)
 out=pathlib.Path(d)/'out'
 if out_exists:out.mkdir()
 e.update(env or {})
 if popen:return subprocess.Popen(['bash',S,*a,'--output',str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=e),log
 r=subprocess.run(['bash',S,*a,'--output',str(out)],capture_output=True,text=True,env=e)
 lines=log.read_text().splitlines() if log.exists() else []
 return r,lines
def has(lines,*parts):return [l for l in lines if all(p in l for p in parts)]
class Refusals(unittest.TestCase):
 def test_syntax(self):self.assertEqual(subprocess.run(['bash','-n',S]).returncode,0)
 def test_requires_explicit_runtime_approval(self):
  r,l=sh('--combined');self.assertEqual(r.returncode,2);self.assertIn('--approve-runtime',r.stderr);self.assertEqual(l,[])
 def test_unsupported_selections_exit_2_and_run_nothing(self):
  for a in (['--component','both'],['--component','suite'],['--component'],[],['--combined','--component','verify'],['--component','verify','--combined'],['--phase','bogus','--combined'],['--bogus']):
   r,l=sh(*a,'--approve-runtime');self.assertEqual(r.returncode,2,a);self.assertEqual(l,[],a)
 def test_split_phase_requires_shared_work_dir(self):
  r,l=sh('--combined','--approve-runtime','--phase','run',work=False);self.assertEqual(r.returncode,2);self.assertEqual(l,[])
class WorkDir(unittest.TestCase):
 def test_work_dir_outside_tmp_is_refused_before_any_work(self):
  for bad in ('/home/runner/work/_temp/conformance-work','/tmp/../home/x','/var/tmp/x'):
   r,l=sh('--combined','--approve-runtime',env={'CONFORMANCE_WORK':bad});self.assertEqual(r.returncode,2,bad);self.assertIn('/tmp',r.stderr);self.assertEqual(l,[],bad)
 def test_workflow_work_dir_is_under_tmp(self):
  t=(ROOT/'.github/workflows/e2e-full-run.yml').read_text();j=t[t.index('  native-combined:'):]
  self.assertNotIn('runner.temp }}/conformance-work',j);self.assertEqual(j.count('CONFORMANCE_WORK: /tmp/conformance-work'),4)
class Routing(unittest.TestCase):
 def test_combined_uses_both_rigs(self):
  r,l=sh('--combined','--approve-runtime');self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(len(has(l,'stage_isolated.py')),2);self.assertEqual(len(has(l,'mvn')),2)
  run=has(l,'run_combined.py');self.assertEqual(len(run),1);self.assertIn('--component both',run[0]);self.assertIn('--certify-classpath',run[0]);self.assertIn('--verify-classpath',run[0])
  self.assertIn('8fdf71656979a72fa8263766d4dec3cc25127b76',' '.join(has(l,'checkout')));self.assertIn('4c4289026968beb535d3dbdd500947152c43f708',' '.join(has(l,'checkout')))
 def test_certify_only_touches_only_certify(self):
  r,l=sh('--component','certify','--approve-runtime');self.assertEqual(r.returncode,0,r.stderr)
  joined=' '.join(l);self.assertNotIn('inji-verify',joined);self.assertNotIn('native-verify',joined);self.assertNotIn('--verify-classpath',joined)
  run=has(l,'run_combined.py')[0];self.assertIn('--component certify',run);self.assertIn('--certify-classpath',run)
  self.assertIn('--component certify',has(l,'stage_isolated.py')[0]);self.assertEqual(len(has(l,'mvn')),1)
 def test_verify_only_touches_only_verify(self):
  r,l=sh('--component','verify','--approve-runtime');self.assertEqual(r.returncode,0,r.stderr)
  joined=' '.join(l);self.assertNotIn('inji-certify',joined);self.assertNotIn('native-certify',joined);self.assertNotIn('--certify-classpath',joined)
  self.assertIn('--component verify',has(l,'run_combined.py')[0])
 def test_phase_run_does_only_the_run(self):
  r,l=sh('--combined','--approve-runtime','--phase','run');self.assertEqual(r.returncode,0);self.assertEqual(len(l),1);self.assertIn('run_combined.py',l[0])
 def test_phase_prepare_does_not_run_or_clean(self):
  r,l=sh('--combined','--approve-runtime','--phase','prepare');self.assertEqual(r.returncode,0)
  self.assertFalse(has(l,'run_combined.py'));self.assertFalse(has(l,'fallback_cleanup.py'));self.assertTrue(has(l,'build_minio.py'));self.assertTrue(has(l,'minio_native_acceptance.py'))
class CleanupAndStatus(unittest.TestCase):
 def test_default_runs_cleanup_then_audit_after_run(self):
  r,l=sh('--combined','--approve-runtime');idx=lambda k:[i for i,x in enumerate(l) if k in x][0]
  self.assertLess(idx('run_combined.py'),idx('fallback_cleanup.py'));self.assertLess(idx('fallback_cleanup.py'),idx('audit_evidence.py'))
 def test_failed_run_still_cleans_audits_and_keeps_status(self):
  r,l=sh('--combined','--approve-runtime',run_exit=1);self.assertEqual(r.returncode,1);self.assertTrue(has(l,'fallback_cleanup.py'));self.assertTrue(has(l,'audit_evidence.py'))
 def test_failed_audit_fails_the_command(self):
  r,l=sh('--combined','--approve-runtime',audit_exit=1);self.assertEqual(r.returncode,2)
 def test_missing_evidence_dir_fails_closed(self):
  r,l=sh('--combined','--approve-runtime','--phase','audit',out_exists=False);self.assertEqual(r.returncode,2);self.assertFalse(has(l,'audit_evidence.py'))
 def test_cleanup_phase_skips_when_nothing_was_started(self):
  r,l=sh('--combined','--approve-runtime','--phase','cleanup',locator=False);self.assertEqual(r.returncode,0);self.assertEqual(l,[])
 def test_cleanup_phase_uses_exact_locator(self):
  r,l=sh('--combined','--approve-runtime','--phase','cleanup');self.assertIn('owned/locator.json',l[0]);self.assertEqual(len(l),1)
class Lifecycle(unittest.TestCase):
 def test_prepare_failure_keeps_exit_code_cleans_and_never_runs(self):
  r,l=sh('--combined','--approve-runtime',env={'SHIM_ACCEPT_EXIT':'7'});self.assertEqual(r.returncode,7)
  self.assertFalse(has(l,'run_combined.py'));self.assertTrue(has(l,'fallback_cleanup.py'));self.assertTrue(has(l,'audit_evidence.py'))
 def test_prepare_failure_before_anything_started_does_not_audit_missing_dir(self):
  r,l=sh('--combined','--approve-runtime',env={'SHIM_ACCEPT_EXIT':'7'},locator=False,out_exists=False);self.assertEqual(r.returncode,7);self.assertEqual(l and [x for x in l if 'fallback' in x or 'audit' in x],[])
 def test_cleanup_failure_is_recorded_and_changes_only_a_zero_exit(self):
  r,l=sh('--combined','--approve-runtime',env={'SHIM_CLEANUP_EXIT':'5'});self.assertEqual(r.returncode,2);self.assertIn('cleanup_failed',r.stderr);self.assertTrue(has(l,'audit_evidence.py'))
  r,l=sh('--combined','--approve-runtime',run_exit=1,env={'SHIM_CLEANUP_EXIT':'5'});self.assertEqual(r.returncode,1);self.assertIn('cleanup_failed',r.stderr)
 def test_audit_failure_after_failed_run_keeps_run_code(self):
  r,l=sh('--combined','--approve-runtime',run_exit=3,audit_exit=1);self.assertEqual(r.returncode,3);self.assertIn('audit_failed',r.stderr)
 def test_term_during_runtime_forwards_then_cleans_and_audits(self):
  import signal,time
  proc,log=sh('--combined','--approve-runtime',env={'SHIM_HANG':'1'},popen=True)
  for _ in range(100):
   if log.exists() and 'run_combined.py' in log.read_text():break
   time.sleep(0.05)
  time.sleep(0.3);proc.send_signal(signal.SIGTERM);out,err=proc.communicate(timeout=20);lines=log.read_text().splitlines()
  self.assertEqual(proc.returncode,143);self.assertTrue(has(lines,'run_combined_got_TERM'))
  idx=lambda k:[i for i,x in enumerate(lines) if k in x][0]
  self.assertLess(idx('run_combined_got_TERM'),idx('fallback_cleanup.py'));self.assertLess(idx('fallback_cleanup.py'),idx('audit_evidence.py'))
class Selection(unittest.TestCase):
 def test_run_combined_selection_table_fails_closed(self):
  import sys;sys.path.insert(0,str(ROOT/'rig-integration'));import run_combined as rc
  self.assertEqual(rc.selected('both'),['certify','verify']);self.assertEqual(rc.selected('certify'),['certify']);self.assertEqual(rc.selected('verify'),['verify'])
  for bad in ('','all','suite',None):
   with self.assertRaises(ValueError):rc.selected(bad)
 def test_workflow_uses_the_script_not_a_copy(self):
  t=(ROOT/'.github/workflows/e2e-full-run.yml').read_text();j=t[t.index('  native-combined:'):]
  self.assertIn('run-full-stack-conformance.sh',j);self.assertNotIn('mvn -q',j);self.assertNotIn('rig-integration/run_combined.py',j);self.assertNotIn('git clone',j)
  self.assertIn('native_component',t);self.assertIn('options: [both, certify, verify]',t);self.assertIn('${NATIVE_COMPONENT:-both}',j)
  self.assertIn("native_component != 'certify' && secrets.GITHUB_TOKEN || ''",j);self.assertIn("--approve-runtime $PH",j)
  import yaml;d=yaml.safe_load(t);i=d[True]['workflow_dispatch']['inputs']['native_component'];self.assertEqual((i['default'],i['options'],i['required']),('both',['both','certify','verify'],False));self.assertEqual(d['jobs']['native-combined']['permissions'],{'contents':'read'})
class MainFailsClosedBeforeAnyStack(unittest.TestCase):
 def test_missing_classpath_for_selected_component_and_bad_selection(self):
  import sys,types;sys.path.insert(0,str(ROOT/'rig-integration'));import run_combined as rc
  base=dict(output='/nonexistent-should-not-be-created',locator='x',java_home='x',minio_image=None,minio_binary=None,minio_provenance=None,certify_classpath=None,verify_classpath=None)
  for comp,extra in (('verify',{}),('certify',{}),('both',{'certify_classpath':'a'}),('suite',{'certify_classpath':'a','verify_classpath':'b'})):
   with self.assertRaises(ValueError):rc.main(types.SimpleNamespace(component=comp,**{**base,**extra}))
  self.assertFalse(pathlib.Path('/nonexistent-should-not-be-created').exists())
if __name__=='__main__':unittest.main()
