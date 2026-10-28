import asyncio,json,pathlib,tempfile,unittest,httpx
import adapter,contract
class Tests(unittest.TestCase):
 def test_happy_bridge_fixture_real_shape_not_live(self):
  async def execute():
   requests=[];transaction=None
   def respond(req):
    nonlocal transaction
    requests.append((req.method,req.url.path))
    if req.url.path.startswith('/api/runner/'):
     return httpx.Response(200,json={'id':'module12345678','name':'oid4vp-1final-verifier-happy-flow','browser':{'uriInputRequests':[{'submitUrl':'https://suite:8443/test/module12345678/authorize'}]}})
    if req.url.path.endswith('/v2/vp-request'):
     body=json.loads(req.content);transaction=body['transactionId'];return httpx.Response(201,json={'transactionId':transaction,'requestId':'req_12345678-abcd-1234-abcd-123456789012','authorizationDetails':{'clientId':contract.CLIENT,'responseUri':contract.RESPONSE,'responseMode':'direct_post','responseType':'vp_token','dcqlQuery':contract.DCQL,'nonce':'abcdef1234567890','responseCodeValidationRequired':False}})
    if req.url.path.endswith('/authorize'):return httpx.Response(200,text='<html>result captured</html>')
    self.assertEqual(json.loads(req.content),contract.RESULT_REQUEST)
    return httpx.Response(200,json={'transactionId':transaction,'allChecksSuccessful':False,'credentialResults':[{'allChecksSuccessful':False,'schemaAndSignatureCheck':{'valid':False,'error':{'message':'secret'}},'expiryCheck':{'valid':True},'holderProofCheck':{'valid':True},'statusCheck':[],'verifiableCredential':'private-token'}]})
   with tempfile.TemporaryDirectory() as tmp:
    bridge=adapter.Adapter(True,tmp);await bridge.http.aclose();bridge.http=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    async def capture(html,module):self.assertTrue(html.exists())
    bridge.capture=capture
    try:
     await bridge('verify','module12345678',None)
     with self.assertRaisesRegex(contract.ContractError,'actual_result_evidence_requires_visual_review'):await bridge('verify','module12345678',None)
     projection=json.loads((pathlib.Path(tmp)/'module12345678-verify-result.json').read_text());self.assertFalse(projection['all_checks_successful']);self.assertNotIn('secret',str(projection));self.assertNotIn('private-token',str(projection));self.assertEqual(sum(p.endswith('/v2/vp-request') for _,p in requests),1);self.assertFalse(bridge.modules['module12345678']['projection']['checks'][0]['status_checks_valid'])
    finally:await bridge.close()
  asyncio.run(execute())
 def test_negative_module_rejected_before_product_mutation(self):
  async def execute():
   with tempfile.TemporaryDirectory() as tmp:
    bridge=adapter.Adapter(True,tmp);await bridge.http.aclose();bridge.http=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'id':'module12345678','name':'negative','browser':{}})))
    try:
     with self.assertRaisesRegex(contract.ContractError,'bridge_unsupported_module'):await bridge('verify','module12345678',None)
     self.assertEqual(bridge.modules,{})
    finally:await bridge.close()
  asyncio.run(execute())
if __name__=='__main__':unittest.main()
