"""Bounded isolated native invocation from a fresh workingdirectory.
All native stdout/stderr discarded because S3Adapter logs test credentials.
"""
import pathlib,subprocess,tempfile,json,shutil,os,signal,re
from owned_process import record
ROOT=pathlib.Path(__file__).resolve().parents[1]
def invoke(component,classpath,java,invocation,output,s3=None,timeout=600):
 output=pathlib.Path(output);output.mkdir(exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='conformance-native-'+component+'-') as directory:
  root=pathlib.Path(directory);(root/'.conformance-isolated').write_text('synthetic-conformance-only');shutil.copytree(ROOT/'rig-integration/isolated-suite',root/'testNgXmlFiles');manifest=root/'invocation.json';manifest.write_text(json.dumps(invocation));os.chmod(manifest,0o600)
  command=[java,'-cp',classpath,'-Dconformance.component='+component,'-Denv.endpoint='+invocation['env_endpoint'],'-Dconformance.invocation='+str(manifest),'-Dconformance.results='+str(root/'results.json')]
  if s3:command.append('-Dconformance.localS3.properties='+str(s3))
  command.append('inji.conformance.IsolatedRigLauncher')
  process=subprocess.Popen(command,cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  record(process)
  try:code=process.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGKILL);process.wait();code=2
  finally:
   if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
  # Copy only native reports and fixedsafe outcomes, never invocation/config/logs.
  if (root/'testng-report').exists():
   native=output/'native-report';native.mkdir()
   for file in (root/'testng-report').iterdir():
    if file.is_file() and (file.name=='testng-results.xml' or re.fullmatch(r'mosip-isolated\.synthetic\.test-inji'+component+r'-[0-9_-]+-(?:full-report|error-report|report)[A-Za-z0-9_-]*\.html',file.name)):
     shutil.copy(file,native/file.name)
  if (root/'results.json').exists():shutil.copy(root/'results.json',output/'conformance-results.json')
  if (root/'local-s3-receipt.json').exists():shutil.copy(root/'local-s3-receipt.json',output/'local-s3-receipt.json')
  (output/'native-outcome.json').write_text(json.dumps({'component':component,'exit_code':code,'mode':'isolated native startTestRunner, not normal full APIregression','s3_required':bool(s3),'s3_readback_verified':(root/'local-s3-receipt.json').exists()}));return code
