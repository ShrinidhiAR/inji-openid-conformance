"""Project-owned result view, never a native Verify UI or certification claim."""
import html,json,pathlib

def render(projection):
 esc=lambda v:html.escape(str(v),quote=True)
 rows=''.join('<tr><td>'+esc(i+1)+'</td><td><pre>'+esc(json.dumps(row,indent=2))+'</pre></td></tr>' for i,row in enumerate(projection['checks']))
 return '<!doctype html><html><head><meta charset="utf-8"><title>Verify API result projection</title><style>body{font:18px Arial;margin:30px;max-width:1100px;color:#172b4d}aside{background:#fff0bf;padding:18px}td{vertical-align:top;padding:14px;border:1px solid #778}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><h1>Verify backend API result</h1><aside>Project-owned view of the actual v2 result API response. This is not the native Verify UI. No claims or credential tokens are shown. Official conformance verdict is separate and is never changed by this view. status_checks_valid null means the API returned no status entries for that credential; it is not a status-check result. This view does not establish certification or trust.</aside><p>Official test ID: '+esc(projection['test_id'])+'</p><p>Matching transaction: '+esc(projection['transaction_matches'])+'</p><p>Credential count: '+esc(projection['credential_count'])+'</p><h2>All checks successful: '+esc(projection['all_checks_successful'])+'</h2><table><tr><th>Credential</th><th>Actual check projection</th></tr>'+rows+'</table></body></html>'
def write(projection,directory,module):
 target=pathlib.Path(directory)/(module+'-verify-result.html');target.write_text(render(projection));return target
