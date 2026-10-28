"""Native api-test integration fixture, NOT live official suite/product evidence.
Usage: python ... --rig-classpath CLASSPATH --component certify|verify --java JAVA
Compile/stage actual pinned api-test and project launcher first.
"""
import argparse,http.server,json,threading,tempfile,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--rig-classpath',required=True);p.add_argument('--component',choices=['certify','verify'],required=True);p.add_argument('--java',default='java');p.add_argument('--s3-properties');p.add_argument('--verdict',choices=['FAILED','PASSED','REVIEW'],default='FAILED');a=p.parse_args();component=a.component
 class H(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   if self.path.startswith('/api/plan?'):v={'id':'plan12345678','name':{'certify':'oid4vci-1_0-issuer-test-plan','verify':'oid4vp-1final-verifier-test-plan'}[component],'modules':[{'testModule':'metadata'}]};status=201
   elif self.path.startswith('/api/runner?'):v={'id':'module12345678','name':'metadata'};status=201
   elif self.path=='/api/runner/module12345678':v={'id':'module12345678','name':'metadata'};status=200
   else:v={};status=404
   self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(v).encode())
  def do_GET(self):
   v={'testId':'module12345678','testName':'metadata','status':'FINISHED','result':a.verdict};self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(v).encode())
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),H);thread=threading.Thread(target=server.serve_forever);thread.start()
 try:
  with tempfile.TemporaryDirectory(prefix='native-rig-fixture-') as directory:
   root=pathlib.Path(directory);(root/'.conformance-isolated').write_text('synthetic-conformance-only');(root/'testNgXmlFiles').mkdir();(root/'testNgXmlFiles/conformanceMasterTestSuite.xml').write_bytes((ROOT/'rig-integration/isolated-suite/conformanceMasterTestSuite.xml').read_bytes())
   endpoint='https://'+component+'.local.test:8443';(root/'config.json').write_text(json.dumps({'vci':{'credential_issuer_url':endpoint}}));(root/'variants.json').write_text('{}')
   invocation={'env_endpoint':endpoint,'verify_service_url':endpoint,'component':component,'runner':str(ROOT/'scripts/conformance_runner.py'),'suite_url':'http://127.0.0.1:'+str(server.server_port),'ca_file':'/etc/ssl/certs/ca-certificates.crt','config':str(root/'config.json'),'variants':str(root/'variants.json'),'run_id':'LOCAL-FIXTURE-NOT-LIVE'};(root/'invocation.json').write_text(json.dumps(invocation))
   command=[a.java,'-cp',a.rig_classpath,'-Dconformance.fixtureOnly=true','-Dconformance.component='+component,'-Denv.endpoint='+endpoint,'-Dconformance.invocation='+str(root/'invocation.json'),'-Dconformance.results='+str(root/'results.json'),'inji.conformance.IsolatedRigLauncher']
   if a.s3_properties:command.insert(-1,'-Dconformance.localS3.properties='+a.s3_properties)
   result=subprocess.run(command,cwd=root,capture_output=True,timeout=100)
   import xml.etree.ElementTree as ET
   report=ET.parse(root/'testng-report/testng-results.xml').getroot();expected=0 if a.verdict=='PASSED' else 1;assert result.returncode==expected and report.get('failed')==str(expected) and report.get('total')=='1'
   assert json.loads((root/'results.json').read_text())[component][0]['result']==a.verdict
   if a.s3_properties:
    receipt=json.loads((root/'local-s3-receipt.json').read_text());assert receipt['native_report_hashes_verified']>=2
    print('PASS LOCAL native MinIO originalreport upload/independenthashreadback '+component+' checked='+str(receipt['native_report_hashes_verified']))
   print('PASS LOCAL native '+component+' discovery/BeforeSuite/official-library-HTTP-FIXTURE/'+a.verdict+'/XMLexit'+str(expected)+'; NOT live suite/product')
 finally:server.shutdown();thread.join()
if __name__=='__main__':main()
