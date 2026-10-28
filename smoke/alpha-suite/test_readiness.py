import tempfile,pathlib,ssl,socket,json,requests,unittest
from readiness import wait,ReadinessFailure,exception,lifecycle,terminal
from proxy_diagnostics import project
class R:
 status_code=502;headers={'Content-Type':'text/html'};content=b'<h1>secret upstream detail</h1>'
 def json(self):raise ValueError('not JSON')
class S:
 def __init__(self,result):self.result=result
 def get(self,*a,**kw):
  if isinstance(self.result,Exception):raise self.result
  return self.result
class Tests(unittest.TestCase):
 def test_http_timeout_keeps_origin(self):
  t=[0]
  with tempfile.TemporaryDirectory() as p:
   out=pathlib.Path(p)
   def sleep(n):t[0]+=n
   with self.assertRaises(ReadinessFailure) as cm:wait(S(R()),'esignet',out,[],cap=10,clock=lambda:t[0],sleep=sleep,inspect_fn=lambda *a:[])
   self.assertEqual(cm.exception.origin,'esignet');self.assertEqual(cm.exception.category,'deadline_http_502')
   rows=[json.loads(x) for x in (out/'readiness.jsonl').read_text().splitlines()]
   self.assertEqual(len(rows),2);self.assertEqual(rows[0]['origin'],'esignet');self.assertEqual(rows[0]['http'],502)
   self.assertNotIn('secret',(out/'readiness.jsonl').read_text())
 def test_terminal_process_prompt(self):
  with tempfile.TemporaryDirectory() as p:
   with self.assertRaises(ReadinessFailure) as cm:wait(S(R()),'certify',pathlib.Path(p),[],cap=180,inspect_fn=lambda *a:[{'service':'tls-gateway','status':'exited','exit_code':1,'oom_killed':False,'health':None}])
   self.assertEqual(cm.exception.category,'terminal_process_state')
 def test_tls_verify_code(self):
  inner=ssl.SSLCertVerificationError(1,'secret cert');inner.verify_code=62
  outer=requests.exceptions.SSLError(inner);e=exception(outer)
  self.assertEqual(e['tls_verify_code'],62);self.assertEqual(e['category'],'hostname_mismatch');self.assertNotIn('secret',json.dumps(e))
  with tempfile.TemporaryDirectory() as p:
   with self.assertRaises(ReadinessFailure) as cm:wait(S(outer),'suite',pathlib.Path(p),[],inspect_fn=lambda *a:[])
   self.assertEqual(cm.exception.category,'hostname_mismatch')
 def test_lifecycle_allowlist(self):
  rows=lifecycle([{'service':'tls-gateway','state':{'Status':'exited','ExitCode':1,'Error':'secret','Health':{'Status':'unhealthy','Log':[{'Output':'secret'}]}}},{'service':'external-secret','state':{}}])
  self.assertEqual(len(rows),1);self.assertNotIn('secret',json.dumps(rows));self.assertTrue(terminal(rows))
  self.assertFalse(terminal(lifecycle([{'service':'initialize','state':{'Status':'exited','ExitCode':0}}])))
 def test_warming_health_not_terminal(self):
  self.assertFalse(terminal([{'status':'running','health':'unhealthy','oom_killed':False,'service':'certify-app','exit_code':0}]))
 def test_dns_chain(self):
  e=exception(requests.ConnectionError(socket.gaierror(-2,'secret hostname')))
  self.assertEqual(e['category'],'dns_error');self.assertNotIn('secret',json.dumps(e))
 def test_changed_http_progress(self):
  t=[0];replies=[R(),requests.ConnectTimeout('secret'),R()]
  class Changing:
   def get(self,*a,**kw):
    r=replies.pop(0)
    if isinstance(r,Exception):raise r
    return r
  with tempfile.TemporaryDirectory() as p:
   out=pathlib.Path(p)
   with self.assertRaises(ReadinessFailure):wait(Changing(),'suite',out,[],cap=15,clock=lambda:t[0],sleep=lambda n:t.__setitem__(0,t[0]+n),inspect_fn=lambda *a:[])
   rows=[json.loads(x) for x in (out/'readiness.jsonl').read_text().splitlines()]
   self.assertEqual([r['category'] for r in rows],['http_response','timeout','http_response','deadline'])
 def test_proxy_projection(self):
  self.assertEqual(project('nginx: host not found in upstream secret.internal /private/key with secret body'),['upstream_dns_unresolved'])
if __name__=='__main__':unittest.main()
