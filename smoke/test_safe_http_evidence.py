import json,tempfile,unittest,pathlib,urllib.error,io
from safe_http_evidence import summarize,Recorder
class Tests(unittest.TestCase):
 def test_up(self):self.assertEqual(summarize('/v1/certify/actuator/health',200,{'Content-Type':'application/vnd.spring-boot.actuator.v3+json' },b'{"status":"UP"}')['health_status'],'UP')
 def test_down_component_no_details(self):
  s=summarize('/actuator/health',503,{},json.dumps({'status':'DOWN','components':{'db':{'status':'DOWN','details':{'password':'SECRET'}},'SECRET':{'status':'UP'}}}))
  self.assertEqual(s['components'],{'db':'DOWN'});self.assertNotIn('SECRET',json.dumps(s))
 def test_actual_mosip_envelope(self):
  s=summarize('/v1/certify/actuator/health',200,{},'{"responseTime":"2026-10-27T17:13:54.056Z","response":null,"errors":[{"errorCode":"unknown_error","errorMessage":"JDBC exception: column cc1_0.claims does not exist"}]}')
  self.assertTrue(s['error_envelope']);self.assertEqual(s['error_codes'],['unknown_error']);self.assertNotIn('JDBC',json.dumps(s))
 def test_http_error(self):
  e=urllib.error.HTTPError('http://localhost/actuator/health',401,'Unauthorized',{'Content-Type':'application/json'},io.BytesIO(b'{"errors":[{"errorCode":"unauthorized","errorMessage":"SECRET"}]}'))
  s=summarize('/actuator/health',e.code,e.headers,e.read());self.assertEqual(s['http'],401);self.assertNotIn('SECRET',json.dumps(s))
 def test_garbage(self):
  for body in [b'',b'<html>SECRET</html>',b'[]',b'null']:
   self.assertNotIn('SECRET',json.dumps(summarize('/actuator/health',404,{},body)))
 def test_hostile_fields(self):
  s=summarize('SECRET',500,{'Content-Type':'SECRET'},json.dumps({'status':'SECRET','errors':[{'errorCode':'SECRET'}]}));self.assertNotIn('SECRET',json.dumps(s))
 def test_changed_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'evidence';r=Recorder(p)
   r.record({'route':'/actuator/health','http':404});r.record({'route':'/actuator/health','http':404});r.record({'route':'/actuator/health','http':200})
   self.assertEqual(len(p.read_text().splitlines()),2)
if __name__=='__main__':unittest.main()
