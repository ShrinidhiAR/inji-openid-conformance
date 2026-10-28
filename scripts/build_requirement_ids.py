"""Regenerate scripts/requirement_ids.txt: spec reference ids that appear as string literals in the pinned public suite source
(network). Prints the list sha256. Only exact members of this list may leave the harness as condition requirement ids."""
import hashlib,io,re,sys,tarfile,urllib.request,pathlib
COMMIT='23353b36957d6466010de767c812d2c91ed37638'
URL='https://gitlab.com/openid/conformance-suite/-/archive/%s/conformance-suite-%s.tar.gz'%(COMMIT,COMMIT)
PAT=re.compile(rb'"((?:OID4VCI|OID4VP|HAIP|FAPI2|OIDCC|RFC|JARM|DPOP|SD-JWT|ISO|OIDF|HTTP|OAuth|OIDC|BCP|OpenID|W3C|IETF|ETSI|ARF|OIDSSF|FAPI1|CIBA)[A-Za-z0-9._-]{0,60})"')
def build():
 data=urllib.request.urlopen(URL,timeout=120).read();ids=set()
 with tarfile.open(fileobj=io.BytesIO(data)) as t:
  for m in t.getmembers():
   if '/src/main/java/' in '/'+m.name and m.name.endswith('.java'):ids.update(x.decode() for x in PAT.findall(t.extractfile(m).read()))
 return ['# Spec reference ids found as string literals under src/main/java, conformance-suite %s. Membership list, one per line.'%COMMIT]+sorted(ids)
if __name__=='__main__':
 text='\n'.join(build())+'\n';print(hashlib.sha256(text.encode()).hexdigest())
 if len(sys.argv)>1:pathlib.Path(sys.argv[1]).write_text(text)
