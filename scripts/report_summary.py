"""Project-owned readable summary; never edits native MOSIP/TestNG evidence."""
import argparse,html,json,pathlib

def render(doc):
 esc=lambda x:html.escape(str(x),quote=True)
 rows=[];details=[]
 for component in ('certify','verify'):
  for i,row in enumerate(doc.get(component,[])):
   anchor=component+'-'+str(i)
   values=[component,row.get('module',''),row.get('test_id',''),row.get('status',''),row.get('result') or '(none)']
   rows.append('<tr>'+''.join('<td>'+('<a href="#'+anchor+'">'+esc(v)+'</a>' if j==1 else esc(v))+'</td>' for j,v in enumerate(values))+'</tr>')
   details.append('<section id="'+anchor+'"><h2>'+esc(component)+' / '+esc(row.get('module',''))+'</h2><dl>'+''.join('<dt>'+esc(k)+'</dt><dd>'+esc(row.get(k,'(none)'))+'</dd>' for k in ('test_id','status','result','harness_category'))+'<dt>condition_verdicts</dt><dd>'+esc('; '.join(c.get('source','')+'='+c.get('result','') for c in row.get('conditions',[])) or '(none recorded)')+'</dd>'+'</dl></section>')
 return '<!doctype html><html><head><meta charset="utf-8"><title>Project conformance summary</title><style>body{font:16px Arial;margin:24px;color:#15202b}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{padding:10px;border:1px solid #9aa6b2;text-align:left;overflow-wrap:anywhere}section{margin-top:28px;padding:16px;border:1px solid #9aa6b2}dd{overflow-wrap:anywhere}aside{padding:14px;background:#fff0bf}</style></head><body><h1>Project conformance summary</h1><aside>This is a project-owned readable view of recorded outcomes. Native MOSIP/TestNG reports are preserved separately. It does not establish full-rig integration or certification.</aside><p>Run: '+esc(doc.get('run',{}).get('id','unknown'))+'</p><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in ('Component','Module','Official test ID','Status','Result'))+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+''.join(details)+'</body></html>'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('results');p.add_argument('output');a=p.parse_args();pathlib.Path(a.output).write_text(render(json.loads(pathlib.Path(a.results).read_text())))
