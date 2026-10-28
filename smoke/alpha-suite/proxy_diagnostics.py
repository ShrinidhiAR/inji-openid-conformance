"""Known nginx stderr categories only. No raw lines, paths, hostnames or secrets."""
import json,subprocess
PATTERNS={'upstream_dns_unresolved':'host not found in upstream','certificate_permission':'Permission denied','certificate_load_failure':'cannot load certificate','key_load_failure':'cannot load certificate key','bind_failure':'bind()','configuration_syntax':'unexpected','upstream_refused':'connect() failed','upstream_timeout':'upstream timed out','upstream_closed':'upstream prematurely closed connection','worker_started':'start worker process'}
def project(raw):return sorted(k for k,v in PATTERNS.items() if v in raw)
def collect(cmd,out):
    r=subprocess.run(cmd+['logs','--no-color','tls-gateway'],capture_output=True,text=True,timeout=15)
    safe={'scope':'controlled tls-gateway logs','read_ok':r.returncode==0,'categories':project(r.stdout+r.stderr)}
    (out/'proxy-diagnostics.json').write_text(json.dumps(safe,indent=2))
