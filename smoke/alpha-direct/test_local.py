import base64,contextlib,io,json,pathlib,shutil,tempfile,unittest
from runtime_signer import prepare
from final_contract import credential_response
from safe_classic import SafeClassic,ProtocolFailure,json_object
from verify_anchor import verify
from cryptography.hazmat.primitives import serialization
class Response:
    status_code=200
    def __init__(self,b):self.b=b
    def json(self):return self.b
class Tests(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(credential_response(200,{'credentials':[{'credential':'fixture'}]}),'fixture')
        for b in ({'credential':'legacy'},{'credentials':[]},{'credentials':['bad']},{'credentials':[{'credential':''}]},{'credentials':[{'credential':'a'},{'credential':'b'}]},{'credentials':[{'credential':'a'}],'errors':[{'message':'secret'}]}):
            with self.assertRaises(ValueError):credential_response(200,b)
    def test_redaction(self):
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured):
            for b in ({'errors':[{'message':'secret-nonce-token'}]},{'error':'secret-nonce-token'},{'response':None}):
                with self.assertRaises(ProtocolFailure) as e:SafeClassic('http://local','http://issuer')._unwrap(Response(b),'secret')
                self.assertNotIn('secret',str(e.exception))
        self.assertEqual(captured.getvalue(),'')
    def test_access_contract(self):
        import jwt,time
        from issue import validate_access,ISSUER,AUD
        from esignet import gen_client_key
        pem,pub,_=gen_client_key();now=int(time.time())
        claims={'iss':ISSUER,'aud':AUD,'sub':'synthetic-subject','client_id':'fixture-client','scope':'sample_vc_mdoc','iat':now-1,'exp':now+60}
        def token(c):return jwt.encode(c,pem,algorithm='ES256',headers={'kid':pub['kid']})
        self.assertTrue(validate_access(token(claims),{'keys':[pub]},'fixture-client')['signature_verified'])
        for field,value in [('iss','wrong'),('aud','wrong'),('client_id','wrong'),('scope','wrong'),('exp',now-60),('iat',now+60),('sub','')]:
            c=dict(claims);c[field]=value
            with self.assertRaises(Exception):validate_access(token(c),{'keys':[pub]},'fixture-client')
        _,other,_=gen_client_key()
        with self.assertRaises(Exception):validate_access(token(claims),{'keys':[other]},'fixture-client')
    def test_runtime_signer(self):
        with tempfile.TemporaryDirectory() as out:
            root,cert=prepare(pathlib.Path(__file__).parents[1]/'alpha-init/config',out)
            try:
                self.assertEqual(root.stat().st_mode&0o777,0o700)
                p=root/'config/certify-mock-mdl.properties';self.assertEqual(p.stat().st_mode&0o777,0o600)
                line=next(x.split('=',1)[1] for x in p.read_text().splitlines() if x.startswith('mosip.certify.mock.mdoc.issuer-key-cert='))
                a,b=line.split('||');key=serialization.load_der_private_key(base64.b64decode(a),password=None)
                self.assertEqual(key.public_key().public_numbers(),cert.public_key().public_numbers())
                self.assertEqual(list(pathlib.Path(out).iterdir())[0].name,'test-issuer-anchor.pem')
                self.assertNotIn('PRIVATE',next(pathlib.Path(out).iterdir()).read_text())
            finally:shutil.rmtree(root)
if __name__=='__main__':unittest.main()
