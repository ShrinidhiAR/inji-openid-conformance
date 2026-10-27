import copy,unittest
from validate_readiness import *
M={'credential_issuer':BASE,'credential_endpoint':BASE+'/v1/certify/issuance/credential','nonce_endpoint':BASE+'/v1/certify/nonce','credential_configurations_supported':{CONFIG:{'format':'mso_mdoc','doctype':'org.iso.18013.5.1.mDL','scope':'sample_vc_mdoc','credential_signing_alg_values_supported':['ES256'],'proof_types_supported':{'jwt':{'proof_signing_alg_values_supported':['ES256']}}}}}
class Tests(unittest.TestCase):
 def test_valid(self): metadata(200,M);health(200,{'status':'UP'});nonce(200,{'c_nonce':'fixture'},{'Cache-Control':'no-store'})
 def test_http(self):
  for code in [201,302,401,500]:
   with self.assertRaises(ValueError):metadata(code,M)
 def test_envelope(self):
  for v in [{'response':None,'errors':[{'errorCode':'unknown_error','errorMessage':'column cc1_0.claims does not exist'}]},[],None,{'response':M},{}]:
   with self.assertRaises(ValueError):metadata(200,v)
 def test_shapes(self):
  for v in [None,[],{},'wrong',42]:
   m=copy.deepcopy(M);m['credential_configurations_supported']=v
   with self.assertRaises(ValueError):metadata(200,m)
 def test_urls(self):
  for k in ['credential_issuer','credential_endpoint','nonce_endpoint']:
   m=copy.deepcopy(M);m[k]='https://wrong.example'
   with self.assertRaises(ValueError):metadata(200,m)
 def test_config(self):
  for k,v in [('format','ldp_vc'),('doctype','wrong'),('scope','wrong'),('credential_signing_alg_values_supported',[]),('proof_types_supported',{})]:
   m=copy.deepcopy(M);m['credential_configurations_supported'][CONFIG][k]=v
   with self.assertRaises(ValueError):metadata(200,m)
 def test_health(self):
  for v in [{'status':'DOWN'},{'errors':['bad']},{}]:
   with self.assertRaises(ValueError):health(200,v)
 def test_nonce(self):
  for v,h in [({},{}),({'c_nonce':None},{}),({'c_nonce':''},{}),({'c_nonce':'x'}, {})]:
   with self.assertRaises(ValueError):nonce(200,v,h)
if __name__=='__main__':unittest.main()
