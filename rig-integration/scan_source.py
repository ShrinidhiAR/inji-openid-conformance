"""Fail-closed source scan before branchpush. Testsentinels are not credentials."""
import pathlib,re,subprocess
patterns=[r'-----BEGIN (?:EC |RSA |ENCRYPTED )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{20,}',r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+']
# Exact pre-existing negativefixtures inspected as literal sentinels, not secrets.
SENTINELS={
 'e2e/scripts/test_esignet_classic.py':{'eyJhbGciOiJFUzI1NiJ9.'+'eyJzdWIiOiJ4In0.AAAA'},
 'smoke/alpha-suite/test_stage_diagnostics.py':{'eyJprivate.'+'token.secret'},
 'smoke/test_safe_exception_causes.py':{'-----BEGIN '+'PRIVATE KEY-----','ghp_'+'abcdefghijklmnopqrst'},
}
bad=[]
for name in subprocess.check_output(['git','ls-files','--cached','-z']).decode().split('\0'):
 if not name:continue
 p=pathlib.Path(name)
 if p.is_file():
  matches={m.group() for pattern in patterns for m in re.finditer(pattern,p.read_text(errors='replace'))}
  if matches-SENTINELS.get(name,set()):bad.append(name)
if bad:raise SystemExit('SOURCE_SECRET_SCAN_FAILED '+','.join(bad))
print('SOURCE_SECRET_SCAN_PASS')
