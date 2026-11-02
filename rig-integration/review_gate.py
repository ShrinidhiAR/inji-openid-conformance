"""Workflow helpers for the live review window. Local files and the owned process only; no product access.
start:        record the owned attempt (pid + start time) and an absolute deadline (call from the launching shell).
wait-pending: block until manifest.json exists, the attempt exits, or the deadline passes; sets pending=true|false.
check-dir:    validate the parsed manifest + image provenance before anything is published.
wait-exit:    wait for the attempt until the shared deadline, print only known evidence prefixes, return its exit code.
terminate:    kill the owned process group only if the recorded pid still has the recorded start time and no exit file exists."""
import argparse,json,os,pathlib,signal,sys,time
PREFIXES=('LIFECYCLE ','HTTP_EVIDENCE ','AS_HTTP ','PASS LOCAL ','COMBINED_')
def exit_code(path):
 p=pathlib.Path(path)
 if not p.exists():return None
 try:return int(p.read_text().strip())
 except ValueError:return 2
def output(name,value):
 f=os.environ.get('GITHUB_OUTPUT')
 if f:open(f,'a').write('%s=%s\n'%(name,value))
 print(name+'='+value)
def start_time(pid):
 try:return pathlib.Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()[19]
 except (OSError,IndexError):return None
def remaining(a,clock=time.time):
 try:end=int(pathlib.Path(a.deadline_file).read_text().strip())
 except (OSError,ValueError,TypeError):return 0
 return min(a.timeout,end-clock())
def wait_pending(a,clock=time.time,sleep=time.sleep):
 d=pathlib.Path(a.dir)
 while remaining(a,clock)>0:
  if (d/'manifest.json').exists():output('pending','true');return 0
  if exit_code(a.exit_file) is not None:break
  sleep(a.interval)
 output('pending','false');return 0
def check_dir(a):
 sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'smoke/verify-final'));import review
 try:review.check_request(a.dir,a.evidence_dir,os.environ.get('GITHUB_RUN_ID',''),time.time())
 except (review.ReviewError,OSError,ValueError,KeyError,TypeError) as e:print('refusing review artifact: '+(str(e) if isinstance(e,review.ReviewError) else 'unreadable'),file=sys.stderr);return 1
 return 0
def wait_exit(a,clock=time.time,sleep=time.sleep):
 while True:
  code=exit_code(a.exit_file)
  if code is not None:
   log=pathlib.Path(a.log)
   if log.exists():
    for line in log.read_text(errors='replace').splitlines():
     if line.startswith(PREFIXES):print(line[:1000])
   return code
  if remaining(a,clock)<=0:print('attempt did not end before the deadline',file=sys.stderr);return 2
  sleep(a.interval)
def terminate(a,kill=os.killpg):
 if exit_code(a.exit_file) is not None:return 0
 try:pid,started=pathlib.Path(a.pid_file).read_text().split()
 except (OSError,ValueError):return 0
 pid=int(pid)
 if start_time(pid)!=started:return 0   # pid reused or gone: not ours
 try:kill(pid,signal.SIGTERM);time.sleep(5);kill(pid,signal.SIGKILL)
 except (ProcessLookupError,PermissionError):pass
 return 0
def main(argv=None):
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
 for n in ('start','wait-pending','check-dir','wait-exit','terminate'):
  q=s.add_parser(n);q.add_argument('--dir');q.add_argument('--evidence-dir');q.add_argument('--pid-file');q.add_argument('--deadline-file');q.add_argument('--exit-file');q.add_argument('--log');q.add_argument('--pid',type=int);q.add_argument('--budget',type=int,default=1500);q.add_argument('--timeout',type=int,default=1500);q.add_argument('--interval',type=int,default=5)
 a=p.parse_args(argv)
 if a.cmd=='start':
  started=start_time(a.pid);
  if started is None:return 1
  pathlib.Path(a.pid_file).write_text('%d %s'%(a.pid,started));pathlib.Path(a.deadline_file).write_text(str(int(time.time())+a.budget));return 0
 return {'wait-pending':wait_pending,'check-dir':check_dir,'wait-exit':wait_exit,'terminate':terminate}[a.cmd](a)
if __name__=='__main__':sys.exit(main())
