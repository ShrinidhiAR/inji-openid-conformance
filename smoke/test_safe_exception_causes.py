import json,unittest
from safe_exception_causes import project,scrub
class Tests(unittest.TestCase):
 def line(self,stack,**kw):return 'app-1 | '+json.dumps({'@timestamp':'t','stack_trace':stack,**kw},separators=(',',':'))
 def test_causes(self):
  s=project(self.line('java.lang.IllegalArgumentException: SECRET\n\tat org.springframework.web.util.ServletRequestPathUtils.getParsedRequestPath(ServletRequestPathUtils.java:77)\nCaused by: io.mosip.certify.SomeException: TOKEN\n\tat io.mosip.certify.advice.ExceptionHandlerAdvice.handleExceptions(ExceptionHandlerAdvice.java:94)'))
  self.assertEqual(len(s[0]['exception_classes']),2);self.assertEqual(s[0]['source_frames'][0]['line'],77);self.assertNotIn('SECRET',json.dumps(s));self.assertNotIn('TOKEN',json.dumps(s))
 def test_structured_jwk(self):self.assertEqual(scrub({'kty':'EC','d':'SECRET','x':'public'})['d'],'<private>')
 def test_message_not_parsed(self):self.assertEqual(project(self.line('',message='java.lang.SecretException: PRIVATE')),[])
 def test_no_namespace_leak(self):self.assertEqual(project(self.line('secret.LeakException: SECRET')),[])
 def test_bad_json(self):self.assertEqual(project('junk {"@timestamp": invalid'),[])
 def test_dedup(self):
  l=self.line('java.lang.IllegalStateException: SECRET');self.assertEqual(len(project(l+'\n'+l)),1)
 def test_redaction(self):
  x=scrub('-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY----- ghp_abcdefghijklmnopqrst');self.assertNotIn('SECRET',x);self.assertNotIn('ghp_',x)
if __name__=='__main__':unittest.main()
