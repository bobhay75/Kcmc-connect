#!/usr/bin/env python3
"""The current functional layer must fail closed for every changed runtime file."""
from pathlib import Path
import shutil,tempfile,unittest
from tony_function_source_layer import FunctionalLayer,ROOT,PREFIX,FIXTURE,MODIFIED,ADDED

class FunctionalProjection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for name in [FIXTURE]+[PREFIX+n for n in MODIFIED|ADDED]:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    def test_exact_preimages_and_added_membership(self):
        layer=FunctionalLayer(self.root)
        self.assertEqual(set(layer.preimages),MODIFIED)
        for name in MODIFIED:self.assertEqual(layer.before(name),layer.fixture['modified'][name]['before_utf8'].encode())
        for name in ADDED:
            with self.assertRaises(AssertionError):layer.before(name)
    def test_each_target_rejects_modified_bytes(self):
        for name in sorted(MODIFIED|ADDED):
            with self.subTest(name=name):
                p=self.root/PREFIX/name;raw=p.read_bytes();p.write_bytes(raw+b'changed')
                with self.assertRaisesRegex(AssertionError,'Only exact Tony functional bytes permitted'):FunctionalLayer(self.root)
                p.write_bytes(raw)
    def test_each_target_rejects_missing_files(self):
        for name in sorted(MODIFIED|ADDED):
            with self.subTest(name=name):
                p=self.root/PREFIX/name;raw=p.read_bytes();p.unlink()
                with self.assertRaises(AssertionError):FunctionalLayer(self.root)
                p.write_bytes(raw)
    def test_fixture_cannot_accept_a_new_runtime_delta(self):
        p=self.root/FIXTURE;p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(AssertionError,'Exact immutable Tony functional fixture'):FunctionalLayer(self.root)
    def test_equal_bytes_in_symlink_hardlink_or_executable_are_refused(self):
        p=self.root/PREFIX/'lib/public-features.php';raw=p.read_bytes();outside=self.root/'outside';outside.write_bytes(raw)
        p.unlink();p.symlink_to(outside)
        with self.assertRaises(AssertionError):FunctionalLayer(self.root)
        p.unlink();p.hardlink_to(outside)
        with self.assertRaises(AssertionError):FunctionalLayer(self.root)
        p.unlink();p.write_bytes(raw);p.chmod(0o755)
        with self.assertRaises(AssertionError):FunctionalLayer(self.root)

if __name__=='__main__':unittest.main(verbosity=2)
