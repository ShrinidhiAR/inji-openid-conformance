import os,pathlib,stat,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import run_native
class T(unittest.TestCase):
 def run_invoke(self,extra):
  with tempfile.TemporaryDirectory() as t:
   t=pathlib.Path(t);java=t/'fakejava';java.write_text('#!/bin/sh\nenv | grep -c "^GITHUB_TOKEN=" > "$FAKE_OUT"\nenv | grep -c "^ACTIONS_RUNTIME_TOKEN=" >> "$FAKE_OUT"\n');java.chmod(java.stat().st_mode|stat.S_IXUSR)
   out=t/'o';os.environ.update({'FAKE_OUT':str(t/'seen'),'GITHUB_TOKEN':'ghs_'+'a'*30,'ACTIONS_RUNTIME_TOKEN':'x'})
   try:
    try:run_native.invoke('verify','cp',str(java),{'env_endpoint':'e'},out,extra_env=extra)
    except Exception:pass
    return (t/'seen').read_text().split()
   finally:
    for k in ('FAKE_OUT','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN'):os.environ.pop(k,None)
 def test_token_only_when_explicitly_passed(self):
  self.assertEqual(self.run_invoke(None),['0','0'])
  self.assertEqual(self.run_invoke({'GITHUB_TOKEN':'ghs_'+'b'*30}),['1','0'])
