"""Pinned Final/DCQL backend API bridge contract. No live deployment claims.
Never logs request/response body, tokens or claims. Not normal UI/session flow.
"""
import json,re,urllib.parse,uuid
SERVICE='https://verify.local.test:8443/v1/verify'
RESPONSE=SERVICE+'/v2/vp-submission/direct-post'
CLIENT='redirect_uri:'+RESPONSE
DCQL={'credentials':[{'id':'pid','format':'dc+sd-jwt','meta':{'vct_values':['urn:eudi:pid:1']},'claims':[{'path':['family_name']}]}]}
FORMATS={'dc+sd-jwt':{'sd-jwt_alg_values':['RS256','ES256','ES256K','EdDSA'],'kb-jwt_alg_values':['RS256','ES256','ES256K','EdDSA']},'vc+sd-jwt':{'sd-jwt_alg_values':['RS256','ES256','ES256K','EdDSA'],'kb-jwt_alg_values':['RS256','ES256','ES256K','EdDSA']},'ldp_vp':{'proof_type':['Ed25519Signature2018','Ed25519Signature2020','RsaSignature2018']}}
RESULT_REQUEST={'skipStatusChecks':False,'statusCheckFilters':[],'includeClaims':False}
class ContractError(ValueError):pass
def require(value,category):
 if not value:raise ContractError(category)
def request(transaction=None):return {'clientId':CLIENT,'transactionId':transaction or str(uuid.uuid4()),'dcqlQuery':DCQL,'responseCodeValidationRequired':False}
def wallet_query(response,transaction):
 require(isinstance(response,dict) and response.get('transactionId')==transaction,'request_transaction')
 rid=response.get('requestId');require(isinstance(rid,str) and re.fullmatch('req_[a-f0-9-]{36}',rid),'request_identifier')
 details=response.get('authorizationDetails');require(isinstance(details,dict) and not response.get('requestUri'),'request_details')
 require(details.get('clientId')==CLIENT and details.get('responseUri')==RESPONSE and details.get('responseMode')=='direct_post' and details.get('responseType')=='vp_token' and details.get('dcqlQuery')==DCQL,'request_profile')
 nonce=details.get('nonce');require(isinstance(nonce,str) and re.fullmatch('[a-zA-Z0-9._~-]{16,}',nonce),'request_nonce')
 require(details.get('responseCodeValidationRequired') is False,'response_code_contract')
 return urllib.parse.urlencode({'client_id':details['clientId'],'state':rid,'response_mode':details['responseMode'],'response_type':details['responseType'],'nonce':nonce,'response_uri':details['responseUri'],'dcql_query':json.dumps(details['dcqlQuery'],separators=(',',':')),'client_metadata':json.dumps({'vp_formats_supported':FORMATS},separators=(',',':'))})
def handoff_url(submit_url,suite,module,query):
 base=urllib.parse.urlsplit(suite);target=urllib.parse.urlsplit(submit_url)
 require(re.fullmatch('[A-Za-z0-9]{8,32}',module),'suite_module_identifier')
 require(base.scheme=='https' and base.hostname=='suite' and base.port==8443 and not base.username,'suite_origin')
 require((target.scheme,target.netloc)==(base.scheme,base.netloc) and target.path=='/test/'+module+'/authorize' and not target.query and not target.fragment and not target.username,'wallet_submit_scope')
 return urllib.parse.urlunsplit((target.scheme,target.netloc,target.path,query,''))
def result_projection(result,transaction):
 require(isinstance(result,dict) and result.get('transactionId')==transaction,'result_transaction')
 rows=result.get('credentialResults');require(isinstance(rows,list) and bool(rows),'empty_credential_results')
 projected=[]
 for row in rows:
  require(isinstance(row,dict),'credential_result_shape')
  checked={key:row.get(key,{}).get('valid') is True for key in ['schemaAndSignatureCheck','expiryCheck','holderProofCheck']}
  status=row.get('statusCheck');require(isinstance(status,list),'status_check_shape')
  # Preserve returned status check structures in private processing only. Public output is booleans/counts.
  checked['status_checks_returned']=len(status)
  checked['status_checks_valid']=bool(status) and all(isinstance(s,dict) and s.get('valid') is True for s in status)
  checked['all_checks_successful']=row.get('allChecksSuccessful') is True
  projected.append(checked)
 return {'transaction_matches':True,'credential_count':len(rows),'all_checks_successful':result.get('allChecksSuccessful') is True,'checks':projected,'source':'Verify v2 result API projection'}
