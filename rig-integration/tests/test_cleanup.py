import unittest,tempfile,pathlib,sys,subprocess,json,types
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from cleanup import cleanup
class Tests(unittest.TestCase):
 def test_down_hosts_minio_fail_still_removes_private_inspects_all_reports(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);private=root/'private';private.mkdir();(private/'secret').write_text('private');out=root/'public';hosts=root/'hosts';hosts.write_text('changed');calls=[]
   def command(args,**kwargs):
    calls.append(args)
    if args[0]=='sudo' or 'compose' in args:raise subprocess.TimeoutExpired('owned',1)
    return subprocess.CompletedProcess(args,0,b'',b'')
   process=types.SimpleNamespace(terminate=lambda:(_ for _ in ()).throw(OSError('private')))
   result=cleanup('owned','compose','original',hosts,private,process,out,command)
   self.assertFalse(result['cleanup_verified']);self.assertFalse(private.exists());self.assertEqual([v for v in ['container','volume','network'] if any(v in c for c in calls)],['container','volume','network']);self.assertTrue((out/'cleanup.json').exists());self.assertNotIn('private',(out/'cleanup.json').read_text().replace('private_removed',''))
 def test_resource_inspection_failure_not_green(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   def command(args,**kwargs):raise OSError('not available')
   result=cleanup('owned',None,None,root/'hosts',None,None,root,command);self.assertFalse(result['cleanup_verified']);self.assertTrue((root/'cleanup.json').exists())
if __name__=='__main__':unittest.main()
