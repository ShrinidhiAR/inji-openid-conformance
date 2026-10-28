"""RealMinIO+native reports, fakeHTTPsuite. Local acceptance, NOTproductproof."""
import argparse,pathlib,tempfile,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));from local_minio import start_binary,create_bucket

def main(args):
 with tempfile.TemporaryDirectory(prefix='native-minio-acceptance-') as directory:
  process,properties=start_binary(directory,args.binary,args.provenance)
  try:
   create_bucket(properties)
   for component,cp in [('certify',args.certify_classpath),('verify',args.verify_classpath)]:
    subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('native_fixture_prototype.py')),'--component',component,'--java',args.java,'--rig-classpath',cp,'--s3-properties',str(properties)],check=True,timeout=100)
  finally:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait()
 print('PASS realMinIOstopped/privateTEMPremoved; officialHTTPsuitefixtureonly')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True);p.add_argument('--provenance',required=True);p.add_argument('--certify-classpath',required=True);p.add_argument('--verify-classpath',required=True);p.add_argument('--java',default='java');main(p.parse_args())
