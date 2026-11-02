"""One fresh synthetic Final issuance. Invoke only after explicit run approval.
No credential, bearer token, proof, nonce, code or private key is written to disk.
"""
import json,pathlib,sys,time,uuid,requests,jwt
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from validate_readiness import metadata,nonce,CONFIG,BASE
from safe_classic import SafeClassic,json_object,ProtocolFailure
from final_contract import credential_response,proof_request
from verify_anchor import verify
from esignet import gen_client_key,_sign_es256
ISSUER='http://esignet:8088';ES='http://localhost:8090'
AUD=ISSUER+'/v1/esignet/vci/credential'

def validate_access(access,jwks,client_id):
    h=jwt.get_unverified_header(access)
    if h.get('alg') not in ('ES256','RS256','PS256'):raise ProtocolFailure('unexpected access algorithm')
    keys=[k for k in jwks.get('keys',[]) if k.get('kid')==h.get('kid')]
    if len(keys)!=1:raise ProtocolFailure('ambiguous access key')
    if any(x in keys[0] for x in ('d','k','p','q','dp','dq','qi','oth')):raise ProtocolFailure('private server JWKS')
    c=jwt.decode(access,jwt.PyJWK.from_dict(keys[0]).key,algorithms=[h['alg']],issuer=ISSUER,audience=AUD,options={'require':['iss','sub','client_id','iat','exp','aud']})
    if c['client_id']!=client_id or not isinstance(c['sub'],str) or not c['sub'] or c['iat']>=time.time() or c.get('scope')!='sample_vc_mdoc':raise ProtocolFailure('access claims mismatch')
    return {'signature_verified':True,'issuer_matches':True,'audience_matches':True,'client_matches':True,'scope_matches':True,'subject_present':True,'time_valid':True}

def seed():
    # Load only constants from the known synthetic seed module, without executing
    # its top-level network operations or its raw-response logger.
    import ast
    tree=ast.parse((HERE.parents[1]/'e2e/scripts/seed_mock_identity.py').read_text())
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='lang' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='body' for t in n.targets)]
    env={'time':time,'INDIVIDUAL':'1774231323','PASSWORD':'Mosip@123'}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'synthetic-seed-data','exec'),env)
    b=json_object(requests.post('http://localhost:8082/v1/mock-identity-system/identity',json=env['body'],timeout=30))
    # Fresh DB only; duplicate/error envelopes fail closed, never treated as seeded.
    if not b.get('response'):raise ProtocolFailure('synthetic identity seed missing response')

def main(out):
    out=pathlib.Path(out);anchor=(out/'test-issuer-anchor.pem').read_bytes()
    stage='synthetic_seed'
    def checkpoint(value):
        (out/'last-stage.json').write_text(json.dumps({'stage':value,'raw_values_retained':False}))
    checkpoint(stage)
    seed()
    md_response=requests.get(BASE+'/v1/certify/.well-known/openid-credential-issuer',timeout=20)
    md=json_object(md_response);cfg=metadata(md_response.status_code,md)
    if md.get('authorization_servers')!=[ISSUER]:raise ProtocolFailure('authorization server metadata mismatch')
    checkpoint('client_registration')
    es=SafeClassic(ES,ISSUER);cid='alpha-direct-'+uuid.uuid4().hex;redirect='http://localhost:18080/callback'
    pem,pub,_=gen_client_key();registration=es._unwrap(es.register_client(cid,[redirect],pub),'register')
    if registration.get('clientId')!=cid:raise ProtocolFailure('registration mismatch')
    checkpoint('classic_authorization')
    code=es.authorization_code_flow(cid,redirect,scope=cfg['scope'])
    checkpoint('token_exchange')
    tokens=es.exchange_code(code,cid,pem,redirect);access=tokens['access_token']
    jwks=json_object(requests.get(ES+'/v1/esignet/oauth/.well-known/jwks.json',timeout=20))
    checkpoint('access_validation')
    claims=validate_access(access,jwks,cid)
    # Fresh nonce immediately before proof+issuance; 40-second cache window.
    checkpoint('alpha_nonce')
    nr=requests.post(md['nonce_endpoint'],timeout=15);nb=json_object(nr);nonce(nr.status_code,nb,nr.headers)
    pp,pk,_=gen_client_key();pk.pop('kid',None)
    proof=_sign_es256(pp,{'alg':'ES256','typ':'openid4vci-proof+jwt','jwk':pk},{'iss':cid,'aud':md['credential_issuer'],'iat':int(time.time()),'nonce':nb['c_nonce']})
    checkpoint('final_credential_request')
    r=requests.post(md['credential_endpoint'],json=proof_request(CONFIG,proof),headers={'Authorization':'Bearer '+access},timeout=60)
    c=credential_response(r.status_code,json_object(r));checkpoint('pinned_credential_verification');verified=verify(c,anchor,pk)
    result={'identity':'synthetic TEST only','release':'1.0.0-alpha.1','deployment':'health-path-adjusted complete alpha DB/config','auth':'classic eSignet1.8.0 Bearer','access_checks':claims,'final_credential_response':True,'credential_checks':verified,'dpop_tested':False,'official_suite_tested':False,'vp_tested':False,'retained':'summary and public anchor only'}
    checkpoint('completed')
    (out/'issuance-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception as e:
        # Never render exception text/trace: HTTP/JWT/crypto errors may carry secrets.
        print('::error::alpha direct issuance failed ('+type(e).__name__+')');sys.exit(1)
