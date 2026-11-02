"""Pinned release-v5.3.4 API projection. No config/body copied to public output."""
import json,re,urllib.parse
PLAN='oid4vci-1_0-issuer-test-plan'
PLAN_ROUTE='/api/plan/info/'+PLAN
MODULES=['oid4vci-1_0-issuer-metadata-test','oid4vci-1_0-issuer-happy-flow']
VARIANT={'fapi_profile':'vci','credential_format':'mdoc','authorization_request_type':'simple','client_auth_type':'private_key_jwt','fapi_request_method':'unsigned','sender_constrain':'dpop','vci_authorization_code_flow_variant':'wallet_initiated','vci_credential_encryption':'plain','vci_grant_type':'authorization_code'}
STATES={'NOT_YET_CREATED','CREATED','CONFIGURED','RUNNING','WAITING','INTERRUPTED','FINISHED'}
RESULTS={'PASSED','FAILED','WARNING','REVIEW','SKIPPED','UNKNOWN'}
class ContractError(RuntimeError):
 def __init__(self,category):self.category=category;super().__init__(category)
def require(ok,category):
 if not ok:raise ContractError(category)
def obj(b):require(isinstance(b,dict) and not b.get('error'),'object_contract');return b
def identifier(v):require(isinstance(v,str) and re.fullmatch('[A-Za-z0-9]{8,32}',v) is not None,'id_contract');return v
def plan_info(b):
 obj(b);require(b.get('planName')==PLAN,'plan_name_contract');require(isinstance(b.get('modules'),list) and isinstance(b.get('variants'),dict),'plan_shape_contract')
 names=[obj(x).get('testModule') for x in b['modules']];require(all(n in names for n in MODULES),'plan_modules_contract')
 for k,v in VARIANT.items():require(v in obj(obj(b['variants'].get(k)).get('variantValues')),'plan_variant_contract')
 require(set(b['variants']['sender_constrain']['variantValues'])=={'mtls','dpop'},'sender_variant_drift');return b
def created_plan(b):
 obj(b);require(b.get('name')==PLAN and isinstance(b.get('modules'),list),'created_plan_contract')
 require(all(n in [obj(x).get('testModule') for x in b['modules']] for n in MODULES),'created_plan_modules_contract');return identifier(b.get('id'))
def created_module(b,name):
 obj(b);require(b.get('name')==name and isinstance(b.get('url'),str),'created_module_contract');return identifier(b.get('id'))
def wait_state(b):
 obj(b);require((set(b)=={'timeout'} and b['timeout'] is True) or (set(b)=={'state'} and b['state'] in STATES),'wait_state_contract');return b.get('state')
def test_info(b,mid,name):
 obj(b);require(b.get('testId')==mid and b.get('testName')==name and b.get('status') in STATES and b.get('result') in RESULTS|{None},'test_info_contract');return b

def implicit_target(html,suite,alias):
 m=re.search(r'''xhr\.open\('POST',\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''',html)
 require(m is not None,'implicit_page_contract');literal=m.group(1)
 try:target=json.loads(literal) if literal.startswith('"') else literal[1:-1].replace('\\/','/')
 except ValueError:raise ContractError('implicit_js_contract') from None
 u=urllib.parse.urlsplit(target);s=urllib.parse.urlsplit(suite)
 require((u.scheme,u.netloc)==(s.scheme,s.netloc) and re.fullmatch('/test/a/'+re.escape(alias)+'/implicit/[A-Za-z0-9]{20}',u.path) is not None and not u.query and not u.fragment,'implicit_target_contract');return target
