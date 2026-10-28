"""Build exact official MinIO source for ephemeral nativeupload acceptance.
Not a production deployment recommendation. Requires Go; starts no service.
"""
import argparse,pathlib,tempfile,urllib.request,hashlib,tarfile,subprocess,json,os
from owned_process import run
COMMIT='9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a'
def build(destination):
 destination=pathlib.Path(destination).resolve()
 if destination.exists():raise ValueError('new_minio_binary_destination_required')
 destination.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='minio-source-build-') as tmp:
  root=pathlib.Path(tmp);archive=root/'source.tar.gz'
  with urllib.request.urlopen('https://codeload.github.com/minio/minio/tar.gz/'+COMMIT,timeout=45) as response:archive.write_bytes(response.read())
  digest=hashlib.sha256(archive.read_bytes()).hexdigest()
  if digest!=SOURCE_ARCHIVE_SHA256:raise ValueError('minio_source_archive_hash')
  with tarfile.open(archive) as tar:
   for member in tar.getmembers():
    if member.issym() or member.islnk() or '..' in pathlib.PurePosixPath(member.name).parts or member.name.startswith('/'):raise ValueError('source_archive_path')
   tar.extractall(root,filter='data')
  source=root/('minio-'+COMMIT)
  result=run(['go','build','-p','4','-trimpath','-o',str(destination),'.'],cwd=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1200)
  if result.returncode:raise ValueError('minio_source_build_failure')
  proof={'source_commit':COMMIT,'source_archive_sha256':digest,'binary_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'go_version':subprocess.check_output(['go','version'],text=True).strip(),'scope':'ephemeral loopback acceptance only, not productiontrust'}
  destination.with_suffix('.provenance.json').write_text(json.dumps(proof,indent=2));return proof
SOURCE_ARCHIVE_SHA256='45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841'
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
