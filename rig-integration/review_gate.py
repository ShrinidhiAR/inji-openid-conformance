"""Workflow helpers for the live review window. No product access; reads local files only.
wait-pending: block until the run writes manifest.json (ready), exits, or times out; sets pending=true|false.
check-dir:   refuse to publish anything except the fixed PNG + manifest pair.
wait-exit:   wait for the background attempt, print only known evidence prefixes, return its exit code."""
import argparse,json,os,pathlib,re,sys,time
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
def wait_pending(a,clock=time.monotonic,sleep=time.sleep):
 end=clock()+a.timeout;d=pathlib.Path(a.dir)
 while clock()<end:
  if (d/'manifest.json').exists():output('pending','true');return 0
  if exit_code(a.exit_file) is not None:break
  sleep(a.interval)
 output('pending','false');return 0
def check_dir(a):
 d=pathlib.Path(a.dir);m=json.loads((d/'manifest.json').read_text());test=m['test_id']
 names=sorted(x.name for x in d.iterdir());want=sorted(['manifest.json',test+'-verify-result.png'])
 if names!=want or any(x.is_symlink() for x in d.iterdir()) or not re.fullmatch('[A-Za-z0-9]{8,32}',test):print('refusing: unexpected review files',file=sys.stderr);return 1
 if (d/(test+'-verify-result.png')).stat().st_size>400*1024:return 1
 return 0
def wait_exit(a,clock=time.monotonic,sleep=time.sleep):
 end=clock()+a.timeout
 while clock()<end:
  code=exit_code(a.exit_file)
  if code is not None:
   log=pathlib.Path(a.log)
   if log.exists():
    for line in log.read_text(errors='replace').splitlines():
     if line.startswith(PREFIXES):print(line[:1000])
   return code
  sleep(a.interval)
 return 2
def main(argv=None):
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
 for n in ('wait-pending','check-dir','wait-exit'):
  q=s.add_parser(n);q.add_argument('--dir');q.add_argument('--exit-file');q.add_argument('--log');q.add_argument('--timeout',type=int,default=1800);q.add_argument('--interval',type=int,default=5)
 a=p.parse_args(argv);return {'wait-pending':wait_pending,'check-dir':check_dir,'wait-exit':wait_exit}[a.cmd](a)
if __name__=='__main__':sys.exit(main())
