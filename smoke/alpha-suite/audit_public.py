"""Fail upload on non-allowlisted file or recognizable secret material."""
import pathlib,re,sys
ALLOW={'suite-api-failure.json','readiness.jsonl','lifecycle.json','proxy-diagnostics.json','run-provenance.json','plan-verification.json','conformance-results.json','condition-verdicts.json','adapter-outcome.json','completion.json','failure.json','cleanup.json','exception-causes.json','tls-ca.pem','certify.local.test.pem','esignet.local.test.pem','suite.local.test.pem','mdoc-test-iaca.pem','mdoc-test-leaf.pem'}
PATTERNS=[r'-----BEGIN (?:EC |RSA |ENCRYPTED )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{20,}',r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',r'"(?:d|k|p|q|dp|dq|qi|oth)"\s*:\s*"[A-Za-z0-9_+/=-]{12,}"']
def audit(root):
 root=pathlib.Path(root);files=list(root.rglob('*'))
 for p in files:
  if not p.is_file():continue
  rel=p.relative_to(root)
  if len(rel.parts)>1:
   if rel.parts[0]!='standalone-report' or p.suffix.lower() not in {'.html','.xml','.json','.js','.css','.png','.gif'}:raise ValueError('unexpected report artifact')
  elif p.name not in ALLOW:raise ValueError('unexpected evidence artifact')
  if p.suffix.lower() not in {'.png','.gif'}:
   text=p.read_text(errors='replace')
   if any(re.search(pat,text,re.S) for pat in PATTERNS):raise ValueError('secret pattern in public evidence')
 print('PUBLIC_EVIDENCE_AUDIT_PASS')
if __name__=='__main__':audit(sys.argv[1])
