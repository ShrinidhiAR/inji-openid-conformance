"""Fail-closed failure-stage projections. Never retain raw event/messages/paths/body."""
import json
SOURCES={'VCICredentialIssuerMetadataValidation','VCIValidateCredentialSigningAlgValuesSupported','RequireIssInAuthorizationResponse','EnsureHttpStatusCodeIsAnyOf','CallProtectedResourceAllowingDpopNonceError'}
CODES={'invalid_token','invalid_request','invalid_proof','invalid_nonce','invalid_credential_request','unsupported_credential_type','unsupported_credential_format','credential_request_denied','use_dpop_nonce','server_error'}
ALGS={'ES256','ES384','ES512','EdDSA','RS256','PS256','-7','-35','-36','-8'}
def project(events):
 out=[]
 for e in events:
  if not isinstance(e,dict) or e.get('src') not in SOURCES:continue
  row={'source':e['src']}
  if e.get('result') in {'SUCCESS','FAILURE','WARNING','INFO'}:row['result']=e['result']
  for key in ('status','http_status'):
   if type(e.get(key)) is int and 100<=e[key]<=599:row['http']=e[key]
  expected=e.get('expected_status_codes')
  if isinstance(expected,list) and expected in ([200,202],[202,200]):row['expected_http']=[200,202]
  if row['source']=='VCICredentialIssuerMetadataValidation':
   es=e.get('invalid_entries');row['schema_details_available']=isinstance(es,list)
   if isinstance(es,list):
    row['invalid_entry_count']=len(es)
    row['mdoc_signing_alg_type_error']=any(isinstance(x,dict) and x.get('path')=='$.credential_configurations_supported.DrivingLicenseCredential.credential_signing_alg_values_supported[0]' and x.get('error')=='string found, integer expected' for x in es)
    row['other_schema_errors_present']=any(not(isinstance(x,dict) and x.get('path')=='$.credential_configurations_supported.DrivingLicenseCredential.credential_signing_alg_values_supported[0]' and x.get('error')=='string found, integer expected') for x in es)
  if row['source']=='VCIValidateCredentialSigningAlgValuesSupported':
   es=e.get('issues');row['algorithm_details_available']=isinstance(es,list)
   if isinstance(es,list):
    row['issue_count']=len(es)
    row['mdoc_string_es256']=('credential_configurations_supported.DrivingLicenseCredential (mso_mdoc): expected COSE integer algorithm identifier, got "ES256"' in es)
  if row['source']=='RequireIssInAuthorizationResponse':
   row['missing_iss']=e.get('msg')=="No 'iss' value in authorization response."
   row['issuer_mismatch']=e.get('msg')=="'iss' parameter in authorization response does not match server's issuer value."
  if row['source']=='CallProtectedResourceAllowingDpopNonceError':
   row['resource_endpoint_matches']=e.get('endpoint_name')=='resource'
   h=e.get('headers');row['headers_available']=isinstance(h,dict)
   if isinstance(h,dict):
    names={k.lower() for k in h if isinstance(k,str)}
    row['dpop_nonce_present']='dpop-nonce' in names;row['www_authenticate_present']='www-authenticate' in names
   b=e.get('body_json')
   if b is None and isinstance(e.get('body'),str):
    try:b=json.loads(e['body'])
    except (ValueError,TypeError):b=None
   row['json_error_code_available']=isinstance(b,dict) and 'error' in b
   if isinstance(b,dict) and 'error' in b:row['error_code']=b['error'] if isinstance(b['error'],str) and b['error'] in CODES else '<other>'
  out.append(row)
 return out

def metadata(md):
 """Controlled config projection from already-fetched metadata, not fixture outcome."""
 c=md.get('credential_configurations_supported',{}).get('DrivingLicenseCredential',{})
 a=c.get('credential_signing_alg_values_supported');out={'format_matches':c.get('format')=='mso_mdoc','algorithm_array':isinstance(a,list)}
 if isinstance(a,list):
  out['algorithm_count']=len(a);out['algorithm_types']=['integer' if type(x) is int else 'string' if isinstance(x,str) else '<other>' for x in a[:10]]
  out['known_algorithm_values']=[x if (type(x) is int and x in {-7,-8,-35,-36}) or (isinstance(x,str) and x in ALGS) else '<other>' for x in a[:10]]
 return out

def browser(details,callback_query,expected_issuer):
 configs=details.get('configs');v=configs.get('issuer') if isinstance(configs,dict) else None
 return {'ui_config_present':isinstance(configs,dict),'ui_issuer_present':isinstance(v,str) and bool(v),'ui_issuer_matches_expected':v==expected_issuer,'callback_has_iss':'iss' in callback_query,'callback_iss_matches_ui':callback_query.get('iss')==v and v is not None}
