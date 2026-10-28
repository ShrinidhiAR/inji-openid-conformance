import contextlib,importlib.util,io,os,pathlib,subprocess,tempfile,time,types,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'review_gate.py';s=importlib.util.spec_from_file_location('g',p);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
def ns(**k):return types.SimpleNamespace(**{'dir':None,'exit_file':None,'log':None,'timeout':10,'interval':0,'deadline_file':None,'pid_file':None,**k})
def deadline(t,delta):f=pathlib.Path(t)/'dl';f.write_text(str(int(time.time())+delta));return str(f)
def out(fn,*a,**k):
 b=io.StringIO()
 with contextlib.redirect_stdout(b):r=fn(*a,**k)
 return r,b.getvalue()
class T(unittest.TestCase):
 def test_wait_exit_prints_only_known_prefixes_and_code(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);(t/'e').write_text('1');(t/'l').write_text('LIFECYCLE []\nsecret=abc\nHTTP_EVIDENCE {}\n')
   code,o=out(g.wait_exit,ns(exit_file=str(t/'e'),log=str(t/'l'),deadline_file=deadline(t,60)))
   self.assertEqual(code,1);self.assertNotIn('secret',o);self.assertIn('LIFECYCLE',o)
 def test_wait_exit_gives_up_at_shared_deadline(self):
  with tempfile.TemporaryDirectory() as t:self.assertEqual(g.wait_exit(ns(exit_file=t+'/none',log=t+'/l',deadline_file=deadline(t,-1))),2)
 def test_missing_deadline_means_no_waiting(self):
  with tempfile.TemporaryDirectory() as t:self.assertEqual(g.wait_exit(ns(exit_file=t+'/none',log=t+'/l',deadline_file=t+'/absent')),2)
 def test_wait_pending_false_when_exit_first_true_when_manifest(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);(t/'e').write_text('0');_,o=out(g.wait_pending,ns(dir=str(t/'r'),exit_file=str(t/'e'),deadline_file=deadline(t,60)));self.assertIn('pending=false',o)
   (t/'r').mkdir();(t/'r'/'manifest.json').write_text('{}');_,o=out(g.wait_pending,ns(dir=str(t/'r'),exit_file=str(t/'x'),deadline_file=deadline(t,60)));self.assertIn('pending=true',o)
 def test_check_dir_refuses_unvalidated_pair(self):
  with tempfile.TemporaryDirectory() as t:
   d=pathlib.Path(t)/'r';d.mkdir();(d/'manifest.json').write_text('{"test_id":"module12345678"}');(d/'module12345678-verify-result.png').write_bytes(b'x')
   os.environ['GITHUB_RUN_ID']='1'
   try:self.assertEqual(g.check_dir(ns(dir=str(d),evidence_dir=t)),1)
   finally:os.environ.pop('GITHUB_RUN_ID')
 def test_terminate_only_owned_unfinished_process(self):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);proc=subprocess.Popen(['sleep','60'],start_new_session=True)
   try:
    g.main(['start','--pid',str(proc.pid),'--pid-file',str(t/'pid'),'--deadline-file',str(t/'dl'),'--budget','60'])
    (t/'pid').write_text('%d 1'%proc.pid)   # wrong start time: pid reuse must be ignored
    g.terminate(ns(pid_file=str(t/'pid'),exit_file=str(t/'e')),kill=lambda *a:self.fail('killed a process that is not ours'))
    self.assertIsNone(proc.poll())
    g.main(['start','--pid',str(proc.pid),'--pid-file',str(t/'pid'),'--deadline-file',str(t/'dl'),'--budget','60'])
    (t/'e').write_text('0');g.terminate(ns(pid_file=str(t/'pid'),exit_file=str(t/'e')),kill=lambda *a:self.fail('attempt already exited'))
    (t/'e').unlink();real=g.time.sleep;g.time.sleep=lambda s:None
    try:g.terminate(ns(pid_file=str(t/'pid'),exit_file=str(t/'e')))
    finally:g.time.sleep=real
    self.assertIsNotNone(proc.wait(timeout=5))
   finally:
    if proc.poll() is None:proc.kill()

class LongBudget(unittest.TestCase):
 def test_budget_2100_is_honoured_by_the_real_helper_with_default_timeout(self):
  # remaining() is min(timeout, deadline-now): the --timeout default (1500) is only a ceiling on a single reading, so waits run until the 2100 s deadline.
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);dl=t/'dl';g.main(['start','--pid',str(os.getpid()),'--pid-file',str(t/'pid'),'--deadline-file',str(dl),'--budget','2100'])
   end=int(dl.read_text());start=end-2100;a=ns(deadline_file=str(dl),timeout=1500)
   self.assertGreater(g.remaining(a,lambda:start+2099),0);self.assertLessEqual(g.remaining(a,lambda:start+2100),0)
   d=t/'rr';d.mkdir();clock=[start]
   def sleep(x):
    clock[0]+=x
    if clock[0]>=start+1700:(d/'manifest.json').write_text('{}')
   out=[];real=g.output;g.output=lambda k,v:out.append((k,v))
   try:g.wait_pending(ns(dir=str(d),exit_file=str(t/'e'),deadline_file=str(dl),timeout=1500,interval=5),lambda:clock[0],sleep)
   finally:g.output=real
   self.assertEqual(out,[('pending','true')])   # a review request 1700 s in (past 1500) is still seen
   out.clear();(d/'manifest.json').unlink();clock[0]=start+2095;g.output=lambda k,v:out.append((k,v))
   try:g.wait_pending(ns(dir=str(d),exit_file=str(t/'e'),deadline_file=str(dl),timeout=1500,interval=5),lambda:clock[0],lambda x:clock.__setitem__(0,clock[0]+x))
   finally:g.output=real
   self.assertEqual(out,[('pending','false')])  # and the wait ends at the deadline
