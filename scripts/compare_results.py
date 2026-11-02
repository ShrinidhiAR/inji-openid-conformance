"""Report-only diff between two combined-results.json files, plus the combined-run gate against a
user-owned expected-failures baseline. Neither mode changes any verdict or evidence. No thresholds
are invented: the baseline is user-authored JSON {"expected":[{"component","module","result", ...}]},
and without it the gate keeps the old behavior (green only when every native rig passes)."""
import argparse,json,pathlib,sys
GREEN=('FINISHED','PASSED')
def rows(doc):
 return {(c,r.get('module')):(r.get('status'),r.get('result')) for c in ('certify','verify') for r in doc.get(c,[]) if isinstance(r,dict)}
def compare(old,new,expected=()):
 a,b=rows(old),rows(new);exp={(e['component'],e['module']):e.get('result') for e in expected}
 out=[]
 for k in sorted(set(a)|set(b),key=str):
  before,after=a.get(k),b.get(k)
  kind='unchanged' if before==after else ('added' if before is None else 'removed' if after is None else 'changed')
  passed=after is not None and after==GREEN
  note='passed' if passed else ('expected_failure' if k in exp and after is not None and after[1]==exp[k] else 'unexpected_not_passed')
  out.append({'component':k[0],'module':k[1],'before':before,'after':after,'change':kind,'classification':note})
 return out
def components(doc):
 sel=doc.get('selected')
 return list(sel) if sel else [c for c in ('certify','verify') if c in doc]
def gate(doc,expected):
 """Judge one combined-results.json against the user-owned baseline. Green only when the run's
 not-green rows match the baseline exactly, scoped to the run's selected components: every not-green
 row must be listed with its exact result (and its exact status/test_id when the entry pins them),
 and every listed entry must still be observed. An entry whose module no longer fails is reported
 as expected_but_not_observed, never silently dropped. The gate sees module, status and result; it
 cannot see which condition failed, so a different failure with the same shape would also match."""
 comps=components(doc)
 exp={}
 for e in expected:
  if e.get('component') in comps:exp[(e.get('component'),e.get('module'))]=e
 matched=[];unexpected=[];hit=set()
 for comp in comps:
  for r in doc.get(comp,[]):
   if not isinstance(r,dict) or (r.get('status'),r.get('result'))==GREEN:continue
   e=exp.get((comp,r.get('module')))
   if e is not None and e.get('result')==r.get('result') and e.get('status') in (None,r.get('status')) and e.get('test_id') in (None,r.get('test_id')):
    matched.append({'component':comp,'module':r.get('module'),'status':r.get('status'),'result':r.get('result'),'reason':e.get('reason')});hit.add((comp,r.get('module')))
   else:
    unexpected.append({'component':comp,'module':r.get('module'),'observed_status':r.get('status'),'observed_result':r.get('result'),'baseline_entry':e})
 missing=[{'component':k[0],'module':k[1],'expected':e} for k,e in sorted(exp.items(),key=str) if k not in hit]
 return {'matches':not unexpected and not missing,'matched_expected_failures':matched,'unexpected_not_passed':unexpected,'expected_but_not_observed':missing}
def main():
 p=argparse.ArgumentParser();p.add_argument('old',nargs='?');p.add_argument('new',nargs='?');p.add_argument('--expected')
 p.add_argument('--gate',action='store_true',help='judge the positional combined-results.json against --expected; exit 0 only when its not-green rows match the baseline exactly')
 g=p.parse_args();exp=json.loads(pathlib.Path(g.expected).read_text()).get('expected',[]) if g.expected else []
 if g.gate:
  if not g.old or not g.expected:p.error('--gate needs one combined-results.json and --expected')
  v=gate(json.loads(pathlib.Path(g.old).read_text()),exp);print(json.dumps(v,indent=2));return 0 if v['matches'] else 1
 if not g.old or not g.new:p.error('diff mode needs two combined-results.json files')
 print(json.dumps(compare(json.loads(pathlib.Path(g.old).read_text()),json.loads(pathlib.Path(g.new).read_text()),exp),indent=2));return 0
if __name__=='__main__':sys.exit(main())
