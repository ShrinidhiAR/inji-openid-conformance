"""Local generated TEST profile. Not live SUT/suite evidence."""
import os,pathlib,ssl,socket,subprocess,tempfile,threading,unittest
from cryptography import x509
from tls_config import tls,NAMES
class Transport(unittest.TestCase):
 def test_strict_generated_profile(self):
  java=os.environ.get('JAVA_HOME','/tmp/jdk21')
  with tempfile.TemporaryDirectory() as p:
   private=pathlib.Path(p)/'private';public=pathlib.Path(p)/'public';private.mkdir(mode=0o700);public.mkdir()
   tls(private,public,java)
   other_private=pathlib.Path(p)/'other-private';other_public=pathlib.Path(p)/'other-public';other_private.mkdir(mode=0o700);other_public.mkdir();tls(other_private,other_public,java)
   ca=x509.load_pem_x509_certificate((public/'tls-ca.pem').read_bytes())
   for host in NAMES:
    leaf=x509.load_pem_x509_certificate((public/(host+'.pem')).read_bytes())
    self.assertEqual(leaf.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier,ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest)
    args=['openssl','verify','-x509_strict','-verify_hostname',host,'-CAfile',str(public/'tls-ca.pem'),str(public/(host+'.pem'))]
    self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)
    args[args.index(host)]='wrong.local.test';self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
    args[args.index('wrong.local.test')]=host;args[args.index(str(public/'tls-ca.pem'))]=str(other_public/'tls-ca.pem');self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
   # Actual Python strict TLS handshake on loopback, no HTTP/no SUT.
   server=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);host=NAMES[0];server.load_cert_chain(str(private/(host+'.pem')),str(private/(host+'.key')))
   client=ssl.create_default_context(cafile=str(public/'tls-ca.pem'));client.verify_flags |= ssl.VERIFY_X509_STRICT
   listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);errors=[]
   def serve():
    try:
     with listener.accept()[0] as raw:
      with server.wrap_socket(raw,server_side=True) as conn:conn.sendall(b'ok')
    except Exception as ex:errors.append(type(ex).__name__)
   th=threading.Thread(target=serve);th.start()
   try:
    with socket.create_connection(listener.getsockname(),timeout=3) as raw:
     with client.wrap_socket(raw,server_hostname=host) as conn:self.assertEqual(conn.recv(2),b'ok')
   finally:th.join(5);listener.close()
   self.assertFalse(th.is_alive());self.assertEqual(errors,[])
if __name__=='__main__':unittest.main()
