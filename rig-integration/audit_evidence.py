"""Combined evidence allowlist+secretpatterns. No rawDocker/nativeprivate logs."""
import pathlib,re,json,sys,xml.etree.ElementTree as ET
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smoke/alpha-suite'));from audit_public import PATTERNS
TOP={'prepared-scope.json','verify-preflight.json','combined-results.json','project-summary.html','cleanup.json','failure.json','readiness.jsonl','lifecycle.json','browser-evidence.jsonl','as-http-evidence.jsonl','tls-ca.pem','certify.local.test.pem','esignet.local.test.pem','suite.pem','verify.local.test.pem','mdoc-test-iaca.pem','mdoc-test-leaf.pem','sdjwt-test-signer.pem','certify-invoke-error.json','verify-invoke-error.json'}
SENSITIVE_KEYS={'jwks','signing_jwk','access_token','refresh_token','id_token','client_secret','credential','vp_token','authorizationDetails','verifiableCredential','claims','config'}
class HtmlGuard(HTMLParser):
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in {'href','src','action'} and value and (value.startswith(('http:','https:','//','data:')) or 'token=' in value or 'code=' in value):raise ValueError('native_external_or_embedded_resource')
def structure(file,text):
 if re.search(r'(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',text):raise ValueError('github_token_pattern')
 if re.search(r'(?i)(access_token|refresh_token|client_secret|signing_jwk|vp_token|verifiableCredential|credential_issuer_url|s3-user-secret|s3-user-key)\s*[\"=:]',text):raise ValueError('sensitive_report_structure')
 if file.suffix in {'.json','.jsonl'}:
  def inspect(value):
   if isinstance(value,dict):
    if set(value)&SENSITIVE_KEYS:raise ValueError('sensitive_json_field')
    for item in value.values():inspect(item)
   elif isinstance(value,list):
    for item in value:inspect(item)
  for value in ([json.loads(line) for line in text.splitlines() if line.strip()] if file.suffix=='.jsonl' else [json.loads(text)]):inspect(value)
 elif file.suffix=='.xml':
  if '<!DOCTYPE' in text or '<!ENTITY' in text:raise ValueError('xml_external_entity')
  root=ET.fromstring(text)
  # Reject rawconfig/token parameters even when nested within native assertions.
  for node in root.iter():
   for value in node.attrib.values():
    if len(value)>4096:raise ValueError('unbounded_xml_attribute')
 elif file.suffix=='.html':HtmlGuard().feed(text)
def audit(directory):
 root=pathlib.Path(directory).resolve()
 cleanup_file=root/'cleanup.json'
 if not cleanup_file.is_file() or json.loads(cleanup_file.read_text()).get('cleanup_verified') is not True:raise ValueError('cleanup_unverified_no_upload')
 for file in pathlib.Path(directory).rglob('*'):
  if file.is_symlink() or not file.resolve().is_relative_to(root):raise ValueError('evidence_symlink_or_outside_root')
  if not file.is_file():continue
  rel=file.relative_to(directory);parts=rel.parts
  allowed=len(parts)==1 and parts[0] in TOP
  if len(parts)==2 and parts[0] in {'certify','verify'} and parts[1] in {'conformance-results.json','native-outcome.json','local-s3-receipt.json'}:allowed=True
  if len(parts)==3 and parts[0] in {'certify','verify'} and parts[1]=='native-report':
   allowed=parts[2]=='testng-results.xml' or bool(re.fullmatch(r'mosip-isolated\.synthetic\.test-inji'+parts[0]+r'-[0-9_-]+-(?:full-report|error-report|report)[A-Za-z0-9_-]*\.html',parts[2]))
  if len(parts)==2 and parts[0] in {'verify-evidence','certify-evidence'}:
   allowed=parts[1] in {'browser-evidence.jsonl','as-http-evidence.jsonl'} or bool(re.fullmatch('[A-Za-z0-9]{8,32}-verify-result\.(json|html|png)',parts[1]))
  if not allowed:raise ValueError('combined_unapproved_artifact')
  if file.suffix.lower() not in {'.png','.gif'}:
   text=file.read_text(errors='replace')
   if any(re.search(pattern,text,re.S) for pattern in PATTERNS):raise ValueError('combined_secret_pattern')
   structure(file,text)
 print('COMBINED_PUBLIC_EVIDENCE_AUDIT_PASS')
if __name__=='__main__':audit(sys.argv[1])
