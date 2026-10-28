"""run-full-stack-conformance.sh routing, argv, cleanup and fail-closed behaviour, with every external command shimmed (nothing real runs)."""
import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];S=str(ROOT/'run-full-stack-conformance.sh')
SHIM='#!/bin/bash\necho "$(basename $0) $*" >> "$SHIM_LOG"\ncase "$(basename $0) $*" in *run_combined.py*) exit ${SHIM_RUN_EXIT:-0};; *audit_evidence.py*) exit ${SHIM_AUDIT_EXIT:-0};; esac\nexit 0\n'
def sh(*a,env=None,work=True,run_exit=0,audit_exit=0,locator=True,out_exists=True):
 d=tempfile.mkdtemp();b=pathlib.Path(d)/'bin';b.mkdir();log=pathlib.Path(d)/'log'
 for n in ('python3','git','mvn'):
  f=b/n;f.write_text(SHIM);f.chmod(0o755)
 w=pathlib.Path(d)/'work'
 for c in ('certify','verify'):
  w.mkdir(exist_ok=True);(w/('native-'+c+'-classpath')).write_text('deps-'+c+'.jar')
 if locator:(w/'owned').mkdir(exist_ok=True);(w/'owned/locator.json').write_text('{}')
 e={'PATH':str(b)+':/usr/bin:/bin','SHIM_LOG':str(log),'JAVA_HOME':'/jdk','SHIM_RUN_EXIT':str(run_exit),'SHIM_AUDIT_EXIT':str(audit_exit)}
 if work:e['CONFORMANCE_WORK']=str(w)
 out=pathlib.Path(d)/'out'
 if out_exists:out.mkdir()
 e.update(env or {})
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
class Selection(unittest.TestCase):
 def test_run_combined_selection_table_fails_closed(self):
  import sys;sys.path.insert(0,str(ROOT/'rig-integration'));import run_combined as rc
  self.assertEqual(rc.selected('both'),['certify','verify']);self.assertEqual(rc.selected('certify'),['certify']);self.assertEqual(rc.selected('verify'),['verify'])
  for bad in ('','all','suite',None):
   with self.assertRaises(ValueError):rc.selected(bad)
 def test_workflow_uses_the_script_not_a_copy(self):
  t=(ROOT/'.github/workflows/e2e-full-run.yml').read_text();j=t[t.index('  native-combined:'):]
  self.assertIn('run-full-stack-conformance.sh',j);self.assertNotIn('mvn -q',j);self.assertNotIn('rig-integration/run_combined.py',j);self.assertNotIn('git clone',j)
class MainFailsClosedBeforeAnyStack(unittest.TestCase):
 def test_missing_classpath_for_selected_component_and_bad_selection(self):
  import sys,types;sys.path.insert(0,str(ROOT/'rig-integration'));import run_combined as rc
  base=dict(output='/nonexistent-should-not-be-created',locator='x',java_home='x',minio_image=None,minio_binary=None,minio_provenance=None,certify_classpath=None,verify_classpath=None)
  for comp,extra in (('verify',{}),('certify',{}),('both',{'certify_classpath':'a'}),('suite',{'certify_classpath':'a','verify_classpath':'b'})):
   with self.assertRaises(ValueError):rc.main(types.SimpleNamespace(component=comp,**{**base,**extra}))
  self.assertFalse(pathlib.Path('/nonexistent-should-not-be-created').exists())
if __name__=='__main__':unittest.main()
