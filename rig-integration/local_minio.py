"""Owned local-only MinIO service configuration; no startup/accountsecret logging.

Requires caller-supplied exact source-built image digest or inspected image lock.
Never fallback silently to a lookalike S3 server or a floating tag.
"""
import pathlib,secrets,os,re

def augment(model,private,image):
 if not re.fullmatch(r'[a-zA-Z0-9./_-]+@sha256:[a-f0-9]{64}',image):raise ValueError('pinned_minio_image_required')
 if 'conformance-minio' in model['services']:raise ValueError('existing_minio_disallowed')
 user='test'+secrets.token_hex(8);password=secrets.token_urlsafe(30)
 model['services']['conformance-minio']={'image':image,'command':['server','/data'],'environment':{'MINIO_ROOT_USER':user,'MINIO_ROOT_PASSWORD':password},'ports':['127.0.0.1:19000:9000'],'tmpfs':['/data'],'networks':['e2e-net']}
 target=pathlib.Path(private)/'local-s3.properties';target.write_text('s3-host=http://127.0.0.1:19000\ns3-region=us-east-1\ns3-account=automationtests\ns3-user-key='+user+'\ns3-user-secret='+password+'\n');os.chmod(target,0o600)
 return target

def create_bucket(properties,timeout=45):
 import boto3,time
 values=dict(line.split('=',1) for line in pathlib.Path(properties).read_text().splitlines());deadline=time.monotonic()+timeout
 client=boto3.client('s3',endpoint_url=values['s3-host'],aws_access_key_id=values['s3-user-key'],aws_secret_access_key=values['s3-user-secret'],region_name='us-east-1',config=__import__('botocore.config',fromlist=['Config']).Config(connect_timeout=2,read_timeout=3,retries={'max_attempts':0}))
 while time.monotonic()<deadline:
  try:client.create_bucket(Bucket='automationtests');client.head_bucket(Bucket='automationtests');return
  except Exception:time.sleep(2)
 raise ValueError('isolated_minio_bucket_not_ready')

def start_binary(private,binary,provenance):
 import hashlib,json,subprocess
 binary=pathlib.Path(binary).resolve();proof=json.loads(pathlib.Path(provenance).read_text())
 if proof.get('source_commit')!='9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a' or proof.get('binary_sha256')!=hashlib.sha256(binary.read_bytes()).hexdigest():raise ValueError('minio_binary_provenance_mismatch')
 user='test'+secrets.token_hex(8);secret=secrets.token_urlsafe(30);private=pathlib.Path(private)
 target=private/'local-s3.properties';target.write_text('s3-host=http://127.0.0.1:19000\ns3-region=us-east-1\ns3-account=automationtests\ns3-user-key='+user+'\ns3-user-secret='+secret+'\n');os.chmod(target,0o600)
 process=subprocess.Popen([str(binary),'server',str(private/'minio-data'),'--address','127.0.0.1:19000','--console-address','127.0.0.1:19001'],env=dict(os.environ,MINIO_ROOT_USER=user,MINIO_ROOT_PASSWORD=secret),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 from owned_process import record
 record(process)
 return process,target
