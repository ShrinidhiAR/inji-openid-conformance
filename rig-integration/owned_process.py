"""Bounded owned command. Never leaves subprocess descendants on timeout."""
import subprocess,os,signal,json,pathlib

def run(command,timeout=60,**kwargs):
 check=kwargs.pop("check",False)
 data=kwargs.pop("input",None)
 if data is not None:kwargs["stdin"]=subprocess.PIPE
 process=subprocess.Popen(command,start_new_session=True,**kwargs)
 try:
  record(process)
  stdout,stderr=process.communicate(input=data,timeout=timeout)
  if check and process.returncode:raise subprocess.CalledProcessError(process.returncode,command)
  return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
 except BaseException:
  try:os.killpg(process.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  process.wait();raise


def record(process):
 path=os.environ.get('CONFORMANCE_RUN_LOCATOR')
 if path:
  locator=pathlib.Path(path);data=json.loads(locator.read_text());stat=pathlib.Path('/proc')/str(process.pid)/'stat'
  if stat.exists():data.setdefault('process_groups',[]).append({'pid':process.pid,'start_time':stat.read_text().split()[21]});locator.write_text(json.dumps(data));os.chmod(locator,0o600)
