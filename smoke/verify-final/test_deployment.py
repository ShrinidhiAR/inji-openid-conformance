import unittest,tempfile,pathlib,json
import deployment
class Tests(unittest.TestCase):
 def test_no_shared_db_or_hostports_and_fresh_synthetic_key(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);private=root/'private';public=root/'public';private.mkdir();public.mkdir()
   config,variant=deployment.signing_config(private,public);self.assertNotIn('d',json.loads((variant).read_text()));self.assertIn('d',json.loads(config.read_text())['credential']['signing_jwk']);self.assertNotIn('PRIVATE KEY',(public/'sdjwt-test-signer.pem').read_text())
   model={'services':{'tls-gateway':{'networks':{'e2e-net':{'aliases':['suite']}},'depends_on':['suite-server']}}};deployment.augment(model,private)
   for name in ('verify-db','verify-schema','verify-app'):self.assertNotIn('ports',model['services'][name]);self.assertNotIn('container_name',model['services'][name])
   self.assertIn('@sha256:',model['services']['verify-app']['image']);self.assertEqual(model['services']['verify-app']['depends_on'],{'verify-schema':{'condition':'service_completed_successfully'}})
   self.assertNotIn('0.18.2',json.dumps(model));self.assertNotIn('DROP ',(deployment.HERE/'db/init.sql').read_text())
if __name__=='__main__':unittest.main()
