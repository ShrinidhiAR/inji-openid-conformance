import json,unittest
from fetch_diagnostics import project,TARGET
class Test(unittest.TestCase):
 def test_allowlist(self):
  e=project([{'src':'VCIGetDynamicCredentialIssuerMetadata','credential_issuer_metadata_endpoint_url':TARGET,'status':404,'error':'private-body','headers':{'private':'secret'},'error_class':'org.springframework.web.client.HttpClientErrorException$NotFound','cause_class':'unknown.secret.Class'},{'src':'VCIGetDynamicCredentialIssuerMetadata','credential_issuer_metadata_endpoint_url':'https://secret.invalid/?token=secret'},{'src':'unrelated','status':500}])
  self.assertEqual(e[0]['http'],404);self.assertEqual(e[0]['http_category'],'not_found');self.assertTrue(e[0]['target_matches_expected']);self.assertFalse(e[1]['target_matches_expected']);self.assertNotIn('secret',json.dumps(e));self.assertNotIn('private',json.dumps(e))
if __name__=='__main__':unittest.main()
