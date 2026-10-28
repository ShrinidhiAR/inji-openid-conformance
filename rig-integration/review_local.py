"""Local human review step for the Verify happy flow, run in a SECOND terminal while the main script waits.
No GitHub, no token. The same hash/run/test/deadline validation as every review source (smoke/verify-final/review.py).
  show     wait for the review request, then print what to open and the exact approve command (never prints the image hash).
  approve  write the approval ONLY when --png-sha256 equals the sha256 of the image you opened (compute it yourself: sha256sum <png>).
Nothing here approves automatically and nothing here changes the suite result: the suite itself ends the module as REVIEW."""
import argparse,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'smoke/verify-final'))
import review
def dirs(work):
 w=pathlib.Path(work);return str(w/'review-request'),str(w/'review-approvals')
def show(a,clock=time.time,sleep=time.sleep,out=print):
 req,_=dirs(a.work);end=clock()+a.wait
 while True:
  try:m,png,(w,h)=review.read_request(req,clock());break
  except review.ReviewError as e:
   if str(e)=='review_artifact_invalid' and not os.path.exists(os.path.join(req,'manifest.json')) and clock()<end:sleep(2);continue
   print('no usable review request: '+str(e),file=sys.stderr);return 1
 left=int(m['deadline']-clock());path=os.path.abspath(os.path.join(req,m['test_id']+'-verify-result.png'))
 out('REVIEW REQUEST READY (project-rendered view of the Verify v2 result API, not the native Verify UI, not certification)')
 out('run: %s  test: %s  image: %dx%d, %d bytes'%(m['run_id'],m['test_id'],w,h,len(png)));out('seconds left in the review window: %d'%left);out('1. open this file and look at it: '+path)
 out('2. compute its hash yourself:  sha256sum '+path);out('3. only if the image is a faithful view, approve with that hash:');out('   python3 rig-integration/review_local.py approve --work %s --png-sha256 <the hash from step 2>'%os.path.abspath(a.work));return 0
def approve(a,clock=time.time,out=print):
 req,ap=dirs(a.work)
 try:target=review.write_local_approval(req,ap,a.png_sha256,clock())
 except review.ReviewError as e:print('not approved: '+str(e),file=sys.stderr);return 1
 out('approval written: '+target);return 0
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
 q=s.add_parser('show');q.add_argument('--work',required=True);q.add_argument('--wait',type=int,default=1500)
 q=s.add_parser('approve');q.add_argument('--work',required=True);q.add_argument('--png-sha256',required=True)
 a=p.parse_args(argv);return {'show':show,'approve':approve}[a.cmd](a)
if __name__=='__main__':sys.exit(main())
