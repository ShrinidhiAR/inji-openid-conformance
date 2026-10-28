"""Workflow always fallback from exact owned locator, no broad dockerprune."""
import argparse,json,pathlib,re,os,signal,subprocess
from cleanup import cleanup

def fallback(locator):
 locator=pathlib.Path(locator).resolve();data=json.loads(locator.read_text());project=data['project'];private=pathlib.Path(data['private']);compose=pathlib.Path(data['compose']);backup=pathlib.Path(data['hosts_backup']);out=pathlib.Path(data['output'])
 if not re.fullmatch('conformance-[a-f0-9]{12}',project):raise ValueError('fallback_project_scope')
 if not private.is_absolute() or not private.resolve().is_relative_to(pathlib.Path('/tmp')) or not compose.resolve().is_relative_to(private.resolve()) or not backup.resolve().is_relative_to(locator.parent):raise ValueError('fallback_private_path_scope')
 # Stop only recorded childprocess identities, verified PIDstarttime preventsreuse.
 for item in data.get('process_groups',[]):
  stat=pathlib.Path('/proc')/str(item['pid'])/'stat'
  if stat.exists() and stat.read_text().split()[21]==item['start_time']:
   try:os.killpg(item['pid'],signal.SIGKILL)
   except ProcessLookupError:pass
 old=backup.read_text() if backup.exists() else None
 result=cleanup(project,compose if compose.exists() else None,old,pathlib.Path('/etc/hosts'),private if private.exists() else None,None,out)
 # Earlier nonzero cleanup must not be hidden by a fallback that cannot verify
 # restoration/privateabsence after an interruption.
 result['private_removed']=not private.exists();result['hosts_restored']=old is not None and pathlib.Path('/etc/hosts').read_text()==old
 result['cleanup_verified']=result.get('down_exit',0)==0 and result['private_removed'] and result['hosts_restored'] and all(result.get(k+'_remaining')==0 for k in ['container','volume','network'])
 (out/'cleanup.json').write_text(json.dumps(result,indent=2));return 0 if result['cleanup_verified'] else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--locator',required=True);args=p.parse_args();raise SystemExit(fallback(args.locator))
