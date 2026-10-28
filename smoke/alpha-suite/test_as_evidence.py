import json,unittest
from safe_esignet import project
class R:
 status_code=200
 def json(self):return {'errors':[{'errorCode':'invalid_redirect_uri','errorMessage':'request.redirectUris[0]: invalid_redirect_uri','rejectedValue':'secret private body'},{'errorCode':'secret-code','errorMessage':'secret-field: leaked-value'}]}
class Test(unittest.TestCase):
 def test_projection(self):
  e=project('/client-mgmt/oauth-client',R());self.assertEqual(e['errors'][0],{'code':'invalid_redirect_uri','field':'request.redirectUris[0]'})
  self.assertNotIn('secret',json.dumps(e));self.assertNotIn('leaked',json.dumps(e))
if __name__=='__main__':unittest.main()
