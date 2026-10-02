import importlib.util, tempfile, unittest, shutil, stat, hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('refresh',ROOT/'contemporary_refresh.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SOURCE=ROOT/'repo/KCMC-Connect-Phase6-Recreated'
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.work=Path(self.tmp.name); self.app=self.work/'app';shutil.copytree(SOURCE,self.app)
  self.backups=self.work/'backups';self.backups.mkdir()
  self.original={n:(self.app/n).read_bytes() for n in m.FILES}
 def apply(self): return m.apply(self.app,self.backups)
 def test_layout_and_scope(self):
  before={str(p.relative_to(self.app)):p.read_bytes() for p in self.app.rglob('*') if p.is_file()};self.apply()
  changed={n for n,v in before.items() if (self.app/n).read_bytes()!=v}
  self.assertEqual(set(m.FILES),changed)
  html=(self.app/'index.php').read_text();self.assertIn(m.NEW_SECTION,html);self.assertNotIn(m.OLD_SECTION,html)
  self.assertIn('420000',(self.app/'public-presentation.js').read_text())
 def test_main_variant_without_optional_family_css(self):
  c=self.app/'public-presentation.css';c.write_text(c.read_text().split('/* Public photo refresh:')[0])
  j=self.app/'public-presentation.js';j.write_text(j.read_text().split("/* Tony's visible photo refresh.")[0])
  self.apply(); self.assertIn(m.FEATURE_CSS,c.read_text())
 def test_existing_caption_patch(self):
  p=self.app/'public-presentation.css';p.write_text(p.read_text()+m.CSS)
  p=self.app/'public-presentation.js';p.write_text(p.read_text().replace(m.OLD_TIMER,m.NEW_TIMER))
  for n in ['index.php','sw.js']:
   p=self.app/n;p.write_text(p.read_text().replace('?v=1.0.0','?v='+m.PRIOR_VERSION))
  self.apply();self.assertEqual((self.app/'public-presentation.css').read_text().count(m.MARKER),2)
 def test_idempotence(self):
  self.apply();self.assertIsNone(self.apply())
 def test_check_no_live_write(self):
  m.apply(self.app,self.backups,True)
  self.assertEqual(self.original,{n:(self.app/n).read_bytes() for n in m.FILES})
 def test_rollback(self):
  b=self.apply();self.assertEqual(m.rollback(self.app,b),4)
  self.assertEqual(self.original,{n:(self.app/n).read_bytes() for n in m.FILES})
 def test_later_edit_refuses_rollback(self):
  b=self.apply();p=self.app/'index.php';p.write_text(p.read_text()+'<!-- later -->')
  with self.assertRaises(m.Stop):m.rollback(self.app,b)
  self.assertTrue(p.read_text().endswith('<!-- later -->'))
 def test_unrelated_edit_preserved(self):
  p=self.app/'index.php';p.write_text(p.read_text().replace('Find your people.','Unrelated owner headline.'))
  self.apply();self.assertIn('Unrelated owner headline.',p.read_text())
 def test_private_logic_unchanged(self):
  b=self.original['index.php'].split(b'?>',1)[0];self.apply()
  self.assertEqual((self.app/'index.php').read_bytes().split(b'?>',1)[0],b)
 def test_modes_preserved(self):
  for n in m.FILES:(self.app/n).chmod(0o644)
  self.apply()
  for n in m.FILES:self.assertEqual(stat.S_IMODE((self.app/n).stat().st_mode),0o644)
 def test_missing_image_stops(self):
  (self.app/'assets/visuals/kcmc-worship-2017.webp').unlink()
  with self.assertRaises(m.Stop):self.apply()
  self.assertEqual(self.original['index.php'],(self.app/'index.php').read_bytes())
 def test_invalid_image_stops(self):
  (self.app/'assets/visuals/kcmc-worship-2017.webp').write_text('not a photo')
  with self.assertRaises(m.Stop):self.apply()
 def test_symlink_refused(self):
  p=self.app/'index.php';p.unlink();p.symlink_to(SOURCE/'index.php')
  with self.assertRaises(m.Stop):self.apply()
 def test_unknown_timer_refused(self):
  p=self.app/'public-presentation.js';p.write_text(p.read_text().replace('}, 8000);','}, 9000);'))
  with self.assertRaises(m.Stop):self.apply()
 def test_edited_target_refused(self):
  p=self.app/'index.php';p.write_text(p.read_text().replace('>Contemporary<br>Worship<','>Different panel<'))
  with self.assertRaises(m.Stop):self.apply()
 def test_unknown_worker_refused(self):
  p=self.app/'sw.js';p.write_text(p.read_text().replace('kcmc-connect-v3.0.3','kcmc-connect-v9'))
  with self.assertRaises(m.Stop):self.apply()
 def test_failed_lint_stops(self):
  with patch.object(m,'lint',side_effect=m.Stop('lint failed')):
   with self.assertRaises(m.Stop):self.apply()
  self.assertEqual(self.original,{n:(self.app/n).read_bytes() for n in m.FILES})
 def test_partial_install_restores(self):
  original_replace=m.os.replace;count=[0]
  def replace(a,b):
   count[0]+=1
   if count[0]==2:raise OSError('simulated I/O failure')
   return original_replace(a,b)
  with patch.object(m.os,'replace',side_effect=replace):
   with self.assertRaises(OSError):self.apply()
  self.assertEqual(self.original,{n:(self.app/n).read_bytes() for n in m.FILES})
 def test_worker_policy_unchanged(self):
  after=m.transform(self.original)
  old=self.original['sw.js'].decode();new=after['sw.js'].decode()
  old=m.versions(old,'test');import re
  old=re.sub(r"^const CACHE='[^']+';", "const CACHE='"+m.CACHE+"';",old)
  self.assertEqual(old,new)
 def test_feature_html_has_no_scripts_or_caption(self):
  self.assertNotIn('<script',m.NEW_SECTION);self.assertNotIn('figcaption',m.NEW_SECTION)
  self.assertNotIn('photo-source',m.NEW_SECTION);self.assertIn('2017',m.NEW_SECTION)
if __name__=='__main__':unittest.main(verbosity=2)
