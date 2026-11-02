"""Stage project integration in a NEW copy of the pinned upstream api-test.

No mutation of originals, no runtime invocation, no network. Compile stagedproject
with Maven, then launch compiledclasses using IsolatedRigLauncher. Runtime still
requires audited invocation manifest and isolatedendpoint/marker.
"""
import argparse,pathlib,shutil,subprocess,tempfile
PINS={'certify':'8fdf71656979a72fa8263766d4dec3cc25127b76','verify':'4c4289026968beb535d3dbdd500947152c43f708'}
ROOT=pathlib.Path(__file__).resolve().parents[1]
def stage(component,upstream,destination):
 upstream=pathlib.Path(upstream).resolve();destination=pathlib.Path(destination).resolve();temp=pathlib.Path(tempfile.gettempdir()).resolve()
 if destination.exists() or temp not in destination.parents:raise ValueError('new_temporary_destination_required')
 sha=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
 if sha!=PINS[component]:raise ValueError('pinned_upstream_required')
 if subprocess.check_output(['git','-C',str(upstream),'status','--porcelain','--untracked-files=no','--','api-test'],text=True).strip():raise ValueError('unmodified_upstream_api_test_required')
 shutil.copytree(upstream/'api-test',destination,ignore=shutil.ignore_patterns('target','.git'))
 (destination/'.conformance-isolated').write_text('synthetic-conformance-only')
 code=destination/'src/main/java/inji/conformance';code.mkdir(parents=True,exist_ok=True)
 shutil.copy(ROOT/'apitestrig-bridge/src/main/java/inji/conformance/ConformanceResultsTest.java',code)
 for p in (ROOT/'rig-integration/src/main/java/inji/conformance').glob('*.java'):shutil.copy(p,code)
 # Existing native API suites must never be discovered in this conformance-only mode.
 suites=destination/'testNgXmlFiles'
 if suites.exists():shutil.rmtree(suites)
 shutil.copytree(ROOT/'rig-integration/isolated-suite',suites)
 return destination
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--component',choices=PINS,required=True);p.add_argument('--upstream',required=True);p.add_argument('--destination',required=True);a=p.parse_args();print(stage(a.component,a.upstream,a.destination))
