import unittest,tempfile,shutil
from pathlib import Path
from kopia.models.project import Project
from kopia.core.ftp import FTPService
from kopia.core.pipeline import safe_component,migrate_legacy_local_file
class Guards(unittest.TestCase):
 def project(self):
  base=Path(tempfile.gettempdir())/'kopia-test'
  return Project(name='Test',host='localhost',username='test',storage_dir=str(base/'s'),daily_backup_dir=str(base/'d'),weekly_backup_dir=str(base/'w'),log_dir=str(base/'l'))
 def test_default_off(self):self.assertFalse(self.project().delete_remote_after_processing)
 def test_root_variants(self):
  for root in ['/','/folder/..','//']:
   p=self.project();p.remote_dir=root;p.delete_remote_after_processing=True;p.delete_confirmation='CANCELLA REMOTO'
   with self.assertRaises(ValueError):p.validate()
 def test_explicit_confirmation(self):
  p=self.project();p.remote_dir='/data';p.delete_remote_after_processing=True
  with self.assertRaises(ValueError):p.validate()
  p.delete_confirmation='CANCELLA REMOTO';p.validate()
 def test_service_blocks_unconfirmed(self):
  p=self.project();p.remote_dir='/data'
  with self.assertRaises(RuntimeError):FTPService(p,None).delete_remote_file_verified('/data/x')
 def test_service_blocks_traversal(self):
  p=self.project();p.remote_dir='/data';p.delete_remote_after_processing=True;p.delete_confirmation='CANCELLA REMOTO'
  with self.assertRaises(RuntimeError):FTPService(p,None).delete_remote_file_verified('/data/../x')
 def test_safe_names(self):
  self.assertEqual(safe_component('A.pdf'),'A.pdf')
  self.assertEqual(safe_component('MX-294'),'MX-294')
  self.assertEqual(safe_component('DP_01'),'DP_01')
  self.assertEqual(safe_component('L294'),'L294')
  self.assertEqual(safe_component('Fascicolo 1'),'Fascicolo 1')
  self.assertNotEqual(safe_component('Fascicolo 1'),'Fascicolo%20%1')
  self.assertNotEqual(safe_component('A.pdf'),safe_component('a.pdf'))
  self.assertNotEqual(safe_component('a/b'), 'a/b')
 def test_nested_backups_rejected(self):
  p=self.project();p.daily_backup_dir=str(Path(p.storage_dir)/'backup')
  with self.assertRaises(ValueError):p.validate()
 def test_legacy_local_name_is_migrated(self):
  base=Path(tempfile.mkdtemp());storage=base/'storage';old=storage/'originals'/'Fascicolo%20%1'/'doc.pdf';new=storage/'originals'/'Fascicolo 1'/'doc.pdf'
  old.parent.mkdir(parents=True);old.write_bytes(b'pdf')
  old_tiff=storage/'tiff'/'Fascicolo%20%1'/'doc.pdf.tiff';old_tiff.parent.mkdir(parents=True);old_tiff.write_bytes(b'tiff')
  try:
   migrate_legacy_local_file({'local':str(old)},new,storage)
   self.assertEqual(new.read_bytes(),b'pdf');self.assertEqual((storage/'tiff'/'Fascicolo 1'/'doc.pdf.tiff').read_bytes(),b'tiff')
   self.assertFalse(old.exists());self.assertFalse(old_tiff.exists())
  finally:shutil.rmtree(base,ignore_errors=True)
if __name__=='__main__':unittest.main()
