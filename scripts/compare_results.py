"""Report-only diff between two combined-results.json files, plus optional user-owned expected-failures.
Does not change any verdict or gate. No thresholds are invented: the expected-failures file is
user-authored JSON {"expected":[{"component","module","result"}]} and is empty/absent by default."""
import argparse,json,pathlib,sys
def rows(doc):
 return {(c,r.get('module')):(r.get('status'),r.get('result')) for c in ('certify','verify') for r in doc.get(c,[]) if isinstance(r,dict)}
def compare(old,new,expected=()):
 a,b=rows(old),rows(new);exp={(e['component'],e['module']):e.get('result') for e in expected}
 out=[]
 for k in sorted(set(a)|set(b),key=str):
  before,after=a.get(k),b.get(k)
  kind='unchanged' if before==after else ('added' if before is None else 'removed' if after is None else 'changed')
  passed=after is not None and after==('FINISHED','PASSED')
  note='passed' if passed else ('expected_failure' if k in exp and after is not None and after[1]==exp[k] else 'unexpected_not_passed')
  out.append({'component':k[0],'module':k[1],'before':before,'after':after,'change':kind,'classification':note})
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('old');p.add_argument('new');p.add_argument('--expected')
 g=p.parse_args();exp=json.loads(pathlib.Path(g.expected).read_text()).get('expected',[]) if g.expected else []
 print(json.dumps(compare(json.loads(pathlib.Path(g.old).read_text()),json.loads(pathlib.Path(g.new).read_text()),exp),indent=2));return 0
if __name__=='__main__':sys.exit(main())
