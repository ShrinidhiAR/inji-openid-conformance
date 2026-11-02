import pathlib,sys,unittest,subprocess,time,os,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));from owned_process import run
class Tests(unittest.TestCase):
 def test_timeout_child_group_killed(self):
  with tempfile.TemporaryDirectory() as tmp:
   pid=pathlib.Path(tmp)/'child.pid'
   command=[sys.executable,'-c','import subprocess,time,pathlib; p=subprocess.Popen(["sleep","60"]);pathlib.Path('+repr(str(pid))+').write_text(str(p.pid));time.sleep(60)']
   with self.assertRaises(subprocess.TimeoutExpired):run(command,timeout=0.5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   time.sleep(0.1);child=int(pid.read_text());stat=pathlib.Path('/proc')/str(child)/'stat';self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z')
 def test_sigterm_parent_reaches_finally_and_child_killed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);marker=root/'cleanup';pid=root/'child';helper=str(pathlib.Path(__file__).resolve().parents[1])
   code='import sys,signal,pathlib;sys.path.insert(0,'+repr(helper)+');from owned_process import run;signal.signal(signal.SIGTERM,lambda s,f:(_ for _ in ()).throw(SystemExit(143)))\ntry:run([sys.executable,"-c",'+repr('import os,pathlib,time;pathlib.Path('+repr(str(pid))+').write_text(str(os.getpid()));time.sleep(60)')+'],timeout=60)\nfinally:pathlib.Path('+repr(str(marker))+').write_text("cleaned")'
   process=subprocess.Popen([sys.executable,'-c',code])
   for _ in range(50):
    if pid.exists():break
    time.sleep(.02)
   process.terminate();self.assertEqual(process.wait(timeout=5),143);self.assertEqual(marker.read_text(),'cleaned');time.sleep(.1)
   stat=pathlib.Path('/proc')/pid.read_text()/'stat';self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z')
 def test_input_and_check(self):
  result=run([sys.executable,'-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],input=b'fixed',stdout=subprocess.PIPE,timeout=2);self.assertEqual(result.stdout,b'fixed')
  with self.assertRaises(subprocess.CalledProcessError):run([sys.executable,'-c','raise SystemExit(1)'],check=True,timeout=2)
if __name__=='__main__':unittest.main()
