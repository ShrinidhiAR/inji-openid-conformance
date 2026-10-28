import unittest,tempfile,pathlib,sys,json,subprocess,types
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import run_native,audit_evidence,run_combined
class Tests(unittest.TestCase):
 def test_audit_rejects_secrets_or_unknown(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);file=root/'cleanup.json';file.write_text('{"cleanup_verified":true}');audit_evidence.audit(root)
   file.write_text('{"cleanup_verified":true,"private":"-----BEGIN PRIVATE KEY-----"}')
   with self.assertRaisesRegex(ValueError,'combined_secret_pattern'):audit_evidence.audit(root)
   file.write_text(json.dumps({'cleanup_verified':True,'client_secret':'sensitive'}))
   with self.assertRaises(ValueError):audit_evidence.audit(root)
   file.write_text('{"cleanup_verified":true}');(root/'config.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'combined_unapproved_artifact'):audit_evidence.audit(root)
 def test_jsonl_sensitive_keys_and_symlinks_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);(root/'cleanup.json').write_text('{"cleanup_verified":true}');row=root/'readiness.jsonl';row.write_text('{"config":{"jwks":{}}}\n')
   with self.assertRaisesRegex(ValueError,'sensitive_json_field'):audit_evidence.audit(root)
   row.unlink();(root/'readiness.jsonl').symlink_to('/etc/hosts')
   with self.assertRaisesRegex(ValueError,'symlink'):audit_evidence.audit(root)
 def test_native_timeout_kills_entire_process_group(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);process=types.SimpleNamespace(pid=56789,poll=lambda: -9,wait=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=[subprocess.TimeoutExpired('jvm',1),-9]))
   with patch.object(run_native.subprocess,'Popen',return_value=process),patch.object(run_native.os,'killpg') as kill:
    result=run_native.invoke('certify','fakecp','java',{'env_endpoint':'https://certify.local.test:8443'},root/'out',timeout=1);self.assertEqual(result,2);kill.assert_called_once()
   self.assertEqual(json.loads((root/'out/native-outcome.json').read_text())['exit_code'],2)
if __name__=='__main__':unittest.main()
