"""Always run existing standalone MOSIP listener on fresh official outcomes.
This is NOT execution inside a full module InjiTestRunner or S3 upload.
"""
import json,pathlib,subprocess,html
ROOT=pathlib.Path(__file__).resolve().parents[2]
def gate(out,run_id):
 out=pathlib.Path(out).resolve();report=ROOT/'apitestrig-bridge/testng-report'
 # Run from separate report working directory to avoid confusing previous output.
 if report.exists():raise RuntimeError('refuse previous report directory')
 cmd=['mvn','-B','-f','pom.xml','compile','exec:java','-Dbenchmark.allowWarnings=false','-Dexec.args=--component certify --results '+str(out/'conformance-results.json')+' --expect-run-id '+run_id]
 r=subprocess.run(cmd,cwd=ROOT/'apitestrig-bridge',capture_output=True,timeout=180)
 summary=report/'gate-summary.json'
 if not summary.exists():raise RuntimeError('MOSIP standalone gate produced no summary')
 b=json.loads(summary.read_text());(out/'adapter-outcome.json').write_text(json.dumps({'exit_code':r.returncode,'report_mode':'standalone MOSIP EmailableReport/TestNG, not full InjiTestRunner/S3','gate_summary':b},indent=2))
 # Original MOSIP report is retained; add visible provenance clarification without
 # changing verdicts or hiding its library metadata.
 for page in report.glob('*.html'):
  text=page.read_text(errors='replace')
  notice='<div style="background:#fff3cd;padding:12px;border:2px solid #856404;font:16px sans-serif">Bounded selected official issuer modules. Run '+html.escape(run_id)+'. Synthetic TEST identity and TEST trust only. Commit/branch in the MOSIP header below identify reporting-library metadata, NOT the tested SUT. See run-provenance.json in parent evidence folder. Standalone MOSIP listener, not full InjiTestRunner or S3.</div>'
  import re
  text=re.sub(r'(<body[^>]*>)',lambda m:m.group(1)+notice,text,count=1,flags=re.I)
  page.write_text(text)
 shutil=__import__('shutil');shutil.copytree(report,out/'standalone-report')
 return r.returncode
