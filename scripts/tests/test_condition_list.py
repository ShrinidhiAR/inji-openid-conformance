import hashlib,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_pinned_list_hash_and_shape(self):
  data=(ROOT/'condition_classes.txt').read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),'4a6b6f7697de1948c2e33b5eb33be26dc175fa314cce7b3d4b01458789352be5')
  lines=data.decode().splitlines();self.assertIn('23353b36957d6466010de767c812d2c91ed37638',lines[0]);self.assertGreater(len(lines),2000);self.assertEqual(len(set(lines[1:])),len(lines)-1)

class Req(unittest.TestCase):
 def test_requirement_ids_are_shape_checked_and_capped(self):
  import sys,pathlib;sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import safe_names as n
  r=n.conditions([{'src':'EnsureHttpStatusCodeIsAnyOf','result':'FAILURE','requirements':['OID4VCI-1FINAL-8.3','bad text with spaces','eyJabc.def.ghi','OID4VCI-secret-not-in-list','OID4VCI-1FINAL-9.2','RFC9449-4','HAIP-1','FAPI2-SP-FINAL-5.3.4-2']}])
  self.assertEqual(r,[{'source':'EnsureHttpStatusCodeIsAnyOf','result':'FAILURE','requirements':['OID4VCI-1FINAL-8.3','OID4VCI-1FINAL-9.2','FAPI2-SP-FINAL-5.3.4-2']}])
  self.assertEqual(n.conditions([{'src':'EnsureHttpStatusCodeIsAnyOf','result':'FAILURE','requirements':'x'}]),[{'source':'EnsureHttpStatusCodeIsAnyOf','result':'FAILURE'}])

 def test_requirement_list_pinned(self):
  import hashlib
  data=(ROOT/'requirement_ids.txt').read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),'75a8822976aafad6ae2acb4195110b1492e912aa933c97628e0382d63938f020')
  import sys;sys.path.insert(0,str(ROOT));import safe_names as n
  self.assertIn('OID4VCI-1FINAL-8.3',n.REQUIREMENT_IDS);self.assertNotIn('OID4VCI-secret-not-in-list',n.REQUIREMENT_IDS);self.assertGreater(len(n.REQUIREMENT_IDS),600)
