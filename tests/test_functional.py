import unittest,tempfile,json,hashlib,shutil,threading,ftplib
from pathlib import Path
from unittest.mock import patch
import pymupdf as fitz
from PIL import Image
from kopia.models.project import Project
from kopia.core import pipeline
from kopia.core.pdf_tiff import convert_pdf_to_tiff_600dpi,compress_pdf_300dpi
from kopia.core.backup import BackupService
from kopia.core.integrity import sha256
from kopia.core.ftp import FTPService
class Silent:
 def write(self,message):pass
class Functional(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  self.p=Project(name='Test',host='localhost',username='test',remote_dir='/data',storage_dir=str(self.base/'storage'),daily_backup_dir=str(self.base/'daily'),weekly_backup_dir=str(self.base/'weekly'),secondary_backup_dir=str(self.base/'secondary'),log_dir=str(self.base/'logs'),daily_keep=1,weekly_keep=1)
 def tearDown(self):self.temp.cleanup()
 def pdf(self,path):
  with fitz.open() as doc:
   for i in range(2):
    page=doc.new_page(width=72,height=72);page.insert_text((5,30),str(i))
   doc.save(path)
 def test_tiff_pages_resolution_original(self):
  pdf=self.base/'x.pdf';self.pdf(pdf);original=sha256(pdf);tiff=self.base/'x.tiff'
  convert_pdf_to_tiff_600dpi(pdf,tiff);compressed=self.base/'compressed.pdf';compress_pdf_300dpi(pdf,compressed)
  self.assertEqual(sha256(pdf),original)
  with Image.open(tiff) as im:
   self.assertEqual(im.n_frames,2)
   for page in range(2):
    im.seek(page);self.assertEqual(im.size,(600,600));self.assertAlmostEqual(im.info['dpi'][0],600)
  with fitz.open(compressed) as doc:
   self.assertEqual(doc.page_count,2)
   self.assertEqual(len(doc[0].get_images(full=True)),1)
   self.assertAlmostEqual(doc[0].rect.width,72,places=1)
   self.assertAlmostEqual(doc[0].rect.height,72,places=1)
   xref=doc[0].get_images(full=True)[0][0]
   self.assertGreater(len(doc.xref_object(xref)), 0)
 def test_full_zip_secondary_retention(self):
  src=self.base/'source';src.mkdir();(src/'file').write_bytes(b'original')
  b=BackupService(Silent());dest=self.base/'backups'
  a,_,_=b.create_full(src,dest,'Test','daily-full');copy=b.secondary_copy(a,self.base/'copy','daily');self.assertEqual(sha256(a),sha256(copy))
  (src/'second').write_bytes(b'cumulative');new,_,count=b.create_full(src,dest,'Test','daily-full');self.assertEqual(count,2)
  b.prune(dest,'Test_daily-full_*.zip',1);self.assertFalse(a.exists());self.assertTrue(new.exists())
 def test_pipeline_repeated_cycle_preserves_original(self):
  pdf=self.base/'source.pdf';self.pdf(pdf);original=pdf.read_bytes();compressed=self.base/'c.pdf';compress_pdf_300dpi(pdf,compressed)
  remote={'/data/a.pdf':original,'/data/sub/file.txt':b'data'};uploads=[]
  class Fake:
   normalize_remote=staticmethod(FTPService.normalize_remote)
   def __init__(self,p,log):pass
   def scan_all(self):return {'files':list(remote),'directories':3,'directory_paths':['/data','/data/sub','/data/empty'],'pdf_count':1,'other_count':1}
   def download_file(self,r,l):Path(l).write_bytes(remote[r])
   def upload_pdf_verified(self,l,r):remote[r]=Path(l).read_bytes();uploads.append(r);return hashlib.sha256(remote[r]).hexdigest()
   def delete_remote_file_verified(self,r):raise AssertionError('Deletion must remain OFF')
  state=self.base/'state';locks=self.base/'locks';state.mkdir();locks.mkdir()
  with patch.object(pipeline,'FTPService',Fake),patch.object(pipeline,'STATE_DIR',state),patch.object(pipeline,'LOCK_DIR',locks),patch.object(pipeline,'Logger',return_value=Silent()),patch.object(pipeline,'ensure_app_dirs'):
   self.assertEqual(pipeline.Pipeline(self.p).run(),0)
   self.assertEqual(pipeline.Pipeline(self.p).run(),0)
   self.assertEqual(pipeline.Pipeline(self.p).run('weekly'),0)
  self.assertEqual(len(uploads),1);self.assertEqual((Path(self.p.storage_dir)/'originals/a.pdf').read_bytes(),original)
  self.assertTrue((Path(self.p.storage_dir)/'originals/empty').is_dir());self.assertTrue((Path(self.p.storage_dir)/'tiff/a.pdf.tiff').is_file())
  self.assertEqual(len(list(Path(self.p.daily_backup_dir).glob('*.zip'))),1)
  self.assertTrue(list(Path(self.p.weekly_backup_dir).glob('*.zip')))
  self.assertFalse(list(Path(self.p.storage_dir).rglob('*.part')))
 def test_upload_hash_rollback(self):
  remote={'/data/x.pdf':b'original'};pdf=self.base/'new.pdf';pdf.write_bytes(b'new')
  class FakeFTP:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def storbinary(self,cmd,f,block):remote[cmd[5:]]=f.read()
   def retrbinary(self,cmd,callback,block):
    name=cmd[5:];callback(b'corrupt' if name=='/data/x.pdf' else remote[name])
   def rename(self,a,b):remote[b]=remote.pop(a)
   def delete(self,name):
    if name not in remote:raise ftplib.error_perm('550 missing')
    del remote[name]
  ftp=FTPService(self.p,Silent())
  with patch.object(ftp,'connect',return_value=FakeFTP()):
   with self.assertRaises(RuntimeError):ftp.upload_pdf_verified(pdf,'/data/x.pdf')
  self.assertEqual(remote,{'/data/x.pdf':b'original'})
if __name__=='__main__':unittest.main()
