"""Private local fixture run of actual published plugin, not live issuer evidence."""
import base64,json,os,pathlib,shutil,subprocess,sys,tempfile
from mdoc_signer import provision
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'alpha-direct'))
from runtime_signer import prepare
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"e2e/scripts"))
from esignet import gen_client_key
from verify_anchor import verify

def check():
 if not pathlib.Path('/tmp/alpha-dto-contract/cp').exists():raise SystemExit('Local published-plugin test requires separately prepared Maven classpath')
 with tempfile.TemporaryDirectory() as out:
  root,_=prepare(pathlib.Path(__file__).parents[1]/'alpha-init/config',out)
  try:
   ca,leaf=provision(root/'config',out);_,pub,_=gen_client_key();did='did:jwk:'+base64.urlsafe_b64encode(json.dumps(pub).encode()).decode().rstrip('=')
   cp=pathlib.Path('/tmp/alpha-dto-contract/cp').read_text()
   r=subprocess.run(['/tmp/jdk21/bin/java','-cp','/tmp/alpha-dto-contract/target/classes:'+cp,'PluginContract',str(root/'config/certify-mock-mdl.properties'),did,str(root/'credential')],capture_output=True)
   if r.returncode:raise RuntimeError('actual plugin test failed '+r.stderr.decode()[-150:])
   credential=(root/'credential').read_text();v=verify(credential,(pathlib.Path(out)/'mdoc-test-leaf.pem').read_bytes(),pub)
   assert v['signature_verified'] and v['holder_key_verified'] and v['digest_count']==8
   print('PASS actual published plugin with independent TEST IACA leaf: signature,8digests,holder,MSOtimes; root out of band')
  finally:shutil.rmtree(root)
if __name__=='__main__':check()
