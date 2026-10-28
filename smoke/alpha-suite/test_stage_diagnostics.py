import json,unittest
from stage_diagnostics import project,metadata,browser
class Diagnostics(unittest.TestCase):
 def test_actual_source_shapes(self):
  rows=project([{'src':'VCICredentialIssuerMetadataValidation','result':'FAILURE','invalid_entries':[{'path':'$.credential_configurations_supported.DrivingLicenseCredential.credential_signing_alg_values_supported[0]','error':'string found, integer expected'}],'input':{'secret':'never'}},{'src':'EnsureHttpStatusCodeIsAnyOf','http_status':401,'expected_status_codes':[202,200]},{'src':'CallProtectedResourceAllowingDpopNonceError','status':401,'endpoint_name':'resource','headers':{'DPoP-Nonce':['never'],'Authorization':['never']},'body':json.dumps({'error':'invalid_token','error_description':'never'})}])
  self.assertTrue(rows[0]['mdoc_signing_alg_type_error']);self.assertFalse(rows[0]['other_schema_errors_present']);self.assertEqual(rows[1]['http'],401);self.assertEqual(rows[2]['error_code'],'invalid_token');self.assertNotIn('never',json.dumps(rows))
 def test_unknown_and_injection_fail_closed(self):
  s='eyJprivate.token.secret'
  rows=project([{'src':'RequireIssInAuthorizationResponse','msg':s,'status':True},{'src':'CallProtectedResourceAllowingDpopNonceError','body':json.dumps({'error':s}),'headers':{s:s}},{'src':s,'http_status':500}])
  self.assertNotIn(s,json.dumps(rows));self.assertNotIn('http',rows[0]);self.assertEqual(rows[1]['error_code'],'<other>');self.assertEqual(len(rows),2)
 def test_metadata_and_bridge(self):
  self.assertEqual(metadata({'credential_configurations_supported':{'DrivingLicenseCredential':{'format':'mso_mdoc','credential_signing_alg_values_supported':['ES256']}}})['known_algorithm_values'],['ES256'])
  d={'configs':{'issuer':'expected'}};self.assertFalse(browser(d,{'code':'private','state':'private'},'expected')['callback_has_iss']);self.assertTrue(browser(d,{'iss':'expected'},'expected')['callback_iss_matches_ui'])
