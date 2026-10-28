"""Every cleanup attempted even if another fails. No rawexception/log export."""
import pathlib,subprocess,shutil,json
from owned_process import run

def cleanup(project,compose,old_hosts,hosts,private,minio_process,out,command=run):
 result={}
 def attempt(name,action):
  try:result[name]=action()
  except BaseException:result[name]='unverified'
 if compose:
  attempt('down_exit',lambda:command(['docker','compose','-p',project,'-f',str(compose),'down','-v','--remove-orphans'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120).returncode)
 if old_hosts is not None:
  def restore():
   r=command(['sudo','tee',str(hosts)],input=old_hosts.encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
   return r.returncode==0 and hosts.read_text()==old_hosts
  attempt('hosts_restored',restore)
 if minio_process:
  def stop():
   try:minio_process.terminate();minio_process.wait(timeout=10)
   except BaseException:
    minio_process.kill();minio_process.wait(timeout=5)
   return minio_process.poll() is not None
  attempt('local_minio_stopped',stop)
 if private:
  def remove():
   shutil.rmtree(private);return not private.exists()
  attempt('private_removed',remove)
 for kind in ('container','volume','network'):
  def inspect(kind=kind):
   r=command(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+project],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15)
   return len(r.stdout.splitlines()) if r.returncode==0 else 'unverified'
  attempt(kind+'_remaining',inspect)
 result['cleanup_verified']=all(value is True or type(value) is int and value==0 for value in result.values()) and bool(result)
 # Last-resort reportdir creation/write independent of other cleanup failure.
 try:out.mkdir(exist_ok=True);(out/'cleanup.json').write_text(json.dumps(result,indent=2))
 except BaseException:result['cleanup_report_written']=False;result['cleanup_verified']=False
 return result
