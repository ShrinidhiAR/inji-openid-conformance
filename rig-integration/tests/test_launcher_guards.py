"""Run guard checks against already-compiled native rig classpath. Local only."""
import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class Guards(unittest.TestCase):
 @unittest.skipUnless(os.environ.get('NATIVE_RIG_TEST_CP'),'set NATIVE_RIG_TEST_CP to compiled launcher/native api-test classpath')
 def test_reject_unrelated_targets_and_suites(self):
  java=os.environ.get('JAVA','java');cp=os.environ['NATIVE_RIG_TEST_CP']
  with tempfile.TemporaryDirectory(prefix='rig-guard-') as directory:
   root=pathlib.Path(directory);(root/'testNgXmlFiles').mkdir();(root/'.conformance-isolated').write_text('synthetic-conformance-only')
   xml=ROOT/'rig-integration/isolated-suite/conformanceMasterTestSuite.xml';(root/'testNgXmlFiles/conformanceMasterTestSuite.xml').write_bytes(xml.read_bytes())
   def call(endpoint):return subprocess.run([java,'-cp',cp,'-Dconformance.component=certify','-Denv.endpoint='+endpoint,'inji.conformance.IsolatedRigLauncher'],cwd=root,capture_output=True,timeout=15)
   for endpoint in ('https://production.example','https://verify.local.test:8443','https://certify.local.test:9443','https://certify.local.test:8443/path','https://user@certify.local.test:8443'):
    r=call(endpoint);self.assertNotEqual(r.returncode,0);self.assertIn(b'isolated_endpoint',r.stderr)
   (root/'testNgXmlFiles/otherMasterTestSuite.xml').write_text('<suite/>');r=call('https://certify.local.test:8443');self.assertIn(b'suite_scope',r.stderr)
   (root/'testNgXmlFiles/otherMasterTestSuite.xml').unlink();(root/'testNgXmlFiles/conformanceMasterTestSuite.xml').write_text('<suite><test><classes><class name="unsafe.Other"/></classes></test></suite>');r=call('https://certify.local.test:8443');self.assertIn(b'suite_contract',r.stderr)
   self.assertFalse((root/'testng-report').exists())
if __name__=='__main__':unittest.main()
