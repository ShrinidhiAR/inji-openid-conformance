import unittest,contract,urllib.parse
class Tests(unittest.TestCase):
 def response(self):
  return {'transactionId':'tx','requestId':'req_12345678-abcd-1234-abcd-123456789012','authorizationDetails':{'clientId':contract.CLIENT,'responseUri':contract.RESPONSE,'responseMode':'direct_post','responseType':'vp_token','dcqlQuery':contract.DCQL,'nonce':'abcdef1234567890','responseCodeValidationRequired':False}}
 def test_real_details_preserved(self):
  query=urllib.parse.parse_qs(contract.wallet_query(self.response(),'tx'));self.assertEqual(query['nonce'],['abcdef1234567890']);self.assertEqual(query['client_id'],[contract.CLIENT])
 def test_modified_response_uri_rejected(self):
  response=self.response();response['authorizationDetails']['responseUri']='https://unrelated.example/submit'
  with self.assertRaisesRegex(contract.ContractError,'request_profile'):contract.wallet_query(response,'tx')
 def test_wallet_origin_and_module_path(self):
  for url in ('https://unrelated.example/test/module12345678/authorize','https://suite:8443/test/other12345678/authorize','https://suite:8443/test/module12345678/authorize?leak=1'):
   with self.assertRaises(contract.ContractError):contract.handoff_url(url,'https://suite:8443','module12345678','state=123')
  self.assertEqual(contract.handoff_url('https://suite:8443/test/module12345678/authorize','https://suite:8443','module12345678','state=123'),'https://suite:8443/test/module12345678/authorize?state=123')
 def test_vacuous_or_wrong_result_rejected(self):
  for result in ({'transactionId':'tx','allChecksSuccessful':True,'credentialResults':[]},{'transactionId':'wrong','credentialResults':[{}]}):
   with self.assertRaises(contract.ContractError):contract.result_projection(result,'tx')
 def test_projection_never_copies_private_material(self):
  row={'schemaAndSignatureCheck':{'valid':True,'error':{'message':'private'}},'holderProofCheck':{'valid':True},'expiryCheck':{'valid':True},'statusCheck':[{'valid':False,'error':{'message':'private'}}],'allChecksSuccessful':False,'verifiableCredential':'secret-token','claims':{'name':'private'}}
  result=contract.result_projection({'transactionId':'tx','credentialResults':[row],'allChecksSuccessful':False},'tx');self.assertNotIn('private',str(result));self.assertNotIn('secret-token',str(result));self.assertFalse(result['checks'][0]['status_checks_valid']);self.assertFalse(result['all_checks_successful'])
if __name__=='__main__':unittest.main()
