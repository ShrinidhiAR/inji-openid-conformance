"""Read raw app logs privately; project only known-namespace exception/frame metadata.

Never emit messages, requests, configuration, source snippets or raw log lines.
Redaction is defense in depth; projection is the disclosure boundary.
"""
import json,re
ROOT=r'(?:java\.|javax\.|jakarta\.|org\.springframework\.|org\.postgresql\.|com\.fasterxml\.|io\.mosip\.|io\.inji\.)'
EX=re.compile(r'(?<![\w.])('+ROOT+r'[A-Za-z0-9_.$]*(?:Exception|Error))(?=[:\s]|$)')
FRAME=re.compile(r'^\s*at\s+('+ROOT+r'[A-Za-z0-9_.$]+)\(([A-Za-z_$][A-Za-z0-9_$]*\.java):(\d{1,6})\)\s*$',re.M)
PRIVATE={'d','k','p','q','dp','dq','qi','oth'}
def scrub(v):
 if isinstance(v,dict):return {k:('<private>' if 'kty' in v and k in PRIVATE else scrub(x)) for k,x in v.items()}
 if isinstance(v,list):return [scrub(x) for x in v]
 if not isinstance(v,str):return v
 v=re.sub(r'-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----.*?-----END (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----','<private>',v,flags=re.S)
 v=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*','<token>',v)
 v=re.sub(r'(?:ghp_|github_pat_)[A-Za-z0-9_]+','<token>',v)
 return v

def project(text):
 result=[];seen=set()
 for raw in text.splitlines():
  start=raw.find('{"@timestamp"')
  if start<0:continue
  try:record=json.loads(raw[start:])
  except ValueError:continue
  record=scrub(record)
  # Only structured stack_trace, not arbitrary messages that could quote data.
  stack=record.get('stack_trace')
  if not isinstance(stack,str):continue
  classes=list(dict.fromkeys(EX.findall(stack)))[:12]
  frames=[{'method':m,'file':f,'line':int(n)} for m,f,n in FRAME.findall(stack)][:24]
  if not classes:continue
  summary={'exception_classes':classes,'source_frames':frames}
  sig=json.dumps(summary,sort_keys=True)
  if sig not in seen:result.append(summary);seen.add(sig)
 return result[:20]
if __name__=='__main__':
 import sys
 print(json.dumps(project(sys.stdin.read()),indent=2))
