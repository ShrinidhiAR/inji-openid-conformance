import datetime,json,pathlib,shutil,sys,tempfile,unittest
from outcomes import document,safe_conditions
from mdoc_signer import provision
from tls_config import tls,augment
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'alpha-direct'))
from runtime_signer import prepare
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
class Tests(unittest.TestCase):
 def test_outcomes(self):
  rows=[{'module':'metadata','test_id':'real-id','status':'FINISHED','result':'FAILED','private':'never retain'}]
  d=document('test-run',datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan-id',rows,['metadata'])
  self.assertEqual(d['certify'][0]['result'],'FAILED');self.assertNotIn('private',json.dumps(d))
  for rr in ([],rows+rows,[dict(rows[0],test_id=None)]):
   with self.assertRaises(ValueError):document('r',datetime.datetime.now(datetime.timezone.utc).isoformat(),'p',rr,['metadata'])
 def test_condition_allowlist(self):
  self.assertEqual(safe_conditions([{'source':'CheckNonce','result':'FAILURE','args':{'private':'secret'},'msg':'nonce=secret'}]),[{'source':'CheckNonce','result':'FAILURE'}])
  self.assertEqual(safe_conditions([{'source':'secret nonce','result':'FAILURE'}]),[])
 def test_callback_scope_guard(self):
  from official_driver import Driver
  import types
  d=Driver('/unused-public-ca');calls=[]
  d.es.par_oauth_details=lambda *args:(calls.append(args) or {'credentialScopes':['wrong-scope']})
  with self.assertRaises(Exception):d.browser('https://esignet.local.test:8443/authorize?client_id=fixture&request_uri=fixture')
  self.assertEqual(len(calls),1)
  with self.assertRaises(Exception):d.browser('https://outside.invalid/authorize?client_id=fixture&request_uri=fixture')
  self.assertEqual(len(calls),1)
 def test_future_provenance(self):
  future=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat()
  with self.assertRaises(ValueError):document('r',future,'p',[{'module':'x','test_id':'fixture','status':'FINISHED','result':'FAILED'}],['x'])
 def test_signer(self):
  with tempfile.TemporaryDirectory() as out:
   root,_=prepare(pathlib.Path(__file__).parents[1]/'alpha-init/config',out)
   try:
    ca,leaf=provision(root/'config',out);self.assertNotEqual(leaf.subject,leaf.issuer)
    ca.public_key().verify(leaf.signature,leaf.tbs_certificate_bytes,ec.ECDSA(leaf.signature_hash_algorithm))
    self.assertTrue(ca.extensions.get_extension_for_class(__import__('cryptography').x509.BasicConstraints).value.ca)
   finally:shutil.rmtree(root)
if __name__=='__main__':unittest.main()
