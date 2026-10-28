"""Regenerate scripts/condition_classes.txt from the pinned public suite source (network). Prints list sha256.
Archive sha256 observed when the list was first built (gzip bytes from GitLab may differ later; the list hash is the check): 41df6fd20f0bcddd21f505ca3b25fdf624bcc5f58d8349b2e59c158d1c5881e1
List file sha256 (excluding nothing): 4a6b6f7697de1948c2e33b5eb33be26dc175fa314cce7b3d4b01458789352be5"""
import hashlib,io,sys,tarfile,urllib.request,pathlib
COMMIT='23353b36957d6466010de767c812d2c91ed37638'
URL='https://gitlab.com/openid/conformance-suite/-/archive/%s/conformance-suite-%s.tar.gz'%(COMMIT,COMMIT)
def build():
 data=urllib.request.urlopen(URL,timeout=60).read();names=set()
 with tarfile.open(fileobj=io.BytesIO(data)) as t:
  for m in t.getmembers():
   if '/src/main/java/net/openid/conformance/condition/' in '/'+m.name and m.name.endswith('.java'):names.add(m.name.rsplit('/',1)[1][:-5])
 return ['# Simple class names under net/openid/conformance/condition, conformance-suite %s (GitLab archive). Membership list, one per line.'%COMMIT]+sorted(names)
if __name__=='__main__':
 text='\n'.join(build())+'\n';print(hashlib.sha256(text.encode()).hexdigest())
 if len(sys.argv)>1:pathlib.Path(sys.argv[1]).write_text(text)
