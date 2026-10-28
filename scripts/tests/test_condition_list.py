import hashlib,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_pinned_list_hash_and_shape(self):
  data=(ROOT/'condition_classes.txt').read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),'4a6b6f7697de1948c2e33b5eb33be26dc175fa314cce7b3d4b01458789352be5')
  lines=data.decode().splitlines();self.assertIn('23353b36957d6466010de767c812d2c91ed37638',lines[0]);self.assertGreater(len(lines),2000);self.assertEqual(len(set(lines[1:])),len(lines)-1)
