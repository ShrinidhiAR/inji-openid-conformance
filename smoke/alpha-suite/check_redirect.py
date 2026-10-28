"""Pinned public libraries, no credentials/network runtime or secret files."""
import hashlib,pathlib,subprocess,tempfile,urllib.request
from official_driver import CALLBACK
LIBS=[('https://repo.maven.apache.org/maven2/io/mosip/esignet/esignet-core/1.8.0/esignet-core-1.8.0.jar','04cb0fe4996ec2a1e9ac5072efee1ca7fd8fcf6053ecbae077b9f2e1ba4c1836'),('https://repo.maven.apache.org/maven2/commons-validator/commons-validator/1.7/commons-validator-1.7.jar','4d74f4ce4fb68b2617edad086df6defdf9338467d2377d2c62e69038e1c4f02f'),('https://repo.maven.apache.org/maven2/jakarta/validation/jakarta.validation-api/3.0.2/jakarta.validation-api-3.0.2.jar','291c25e6910cc6a7ebd96d4c6baebf6d7c37676c5482c2d96146e901b62c1fc9')]
def main():
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);jars=[]
  for i,(url,expected) in enumerate(LIBS):
   p=root/(str(i)+'.jar');urllib.request.urlretrieve(url,p)
   if expected and hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('public dependency digest mismatch')
   jars.append(str(p))
  cp=':'.join(jars);source=pathlib.Path(__file__).with_name('RedirectContract.java')
  subprocess.run(['javac','-proc:none','-cp',cp,'-d',str(root),str(source)],check=True,capture_output=True)
  r=subprocess.run(['java','-cp',str(root)+':'+cp,'RedirectContract',CALLBACK],check=True,capture_output=True,text=True)
  print(r.stdout.strip())
if __name__=='__main__':main()
