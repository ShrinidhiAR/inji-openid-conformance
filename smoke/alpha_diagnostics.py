import json,pathlib,subprocess,re
from safe_exception_causes import project
out=pathlib.Path('smoke-out');out.mkdir(exist_ok=True)
p=subprocess.run(['docker','compose','-f','smoke/alpha-init/compose.yaml','logs','--no-color','certify-app','initialize','certify-db'],capture_output=True,text=True)
# Read complete container logs internally, project causes before truncation.
(out/'exception-causes.json').write_text(json.dumps(project(p.stdout),indent=2))
summaries=[]
for line in p.stdout.splitlines():
 if '{"@timestamp"' in line:
  try:
   m=json.loads(line[line.index('{"@timestamp"'):]);msg=m.get('message','')
   # Keep only known fixed diagnostics; no free-form data.
   if any(x in msg for x in ['Started CertifyServiceApplication','KEY CHECK','Application run failed','Shutdown completed']):summaries.append({'time':m.get('@timestamp'),'level':m.get('level'),'message':msg[:220]})
  except ValueError:pass
 elif any(x in line for x in ['ERROR:','FATAL:','COPY 8','CREATE TABLE','DO']):
  # DB statements/status only, redact quoted content and long opaque strings.
  line=re.sub(r"'[^']*'",'<quoted>',line);line=re.sub(r'[A-Za-z0-9_+/=-]{45,}','<opaque>',line)
  summaries.append({'database_diagnostic':line[:240]})
(out/'diagnostics.json').write_text(json.dumps(summaries,indent=2))
print('Saved bounded allowlisted diagnostic summaries, not raw logs')
