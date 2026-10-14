import ftplib,ssl,posixpath,hashlib,uuid
from pathlib import Path
class FTPService:
 def __init__(self,p,logger):self.p=p;self.log=logger
 @staticmethod
 def normalize_remote(path):
  path=str(path).strip()
  if any(c in path for c in ('\r','\n','\x00','\\')):raise ValueError('Percorso FTP non valido')
  return posixpath.normpath('/'+path.lstrip('/'))
 def connect(self):
  cls=ftplib.FTP_TLS if self.p.use_ftps else ftplib.FTP;options={'timeout':self.p.timeout}
  if self.p.use_ftps:
   ctx=ssl.create_default_context()
   if not self.p.verify_tls:ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
   options['context']=ctx
  ftp=cls(**options)
  try:
   ftp.connect(self.p.host,int(self.p.port));ftp.login(self.p.username,self.p.password)
   if self.p.use_ftps:ftp.prot_p()
   ftp.set_pasv(self.p.passive);ftp.voidcmd('TYPE I');return ftp
  except Exception:ftp.close();raise
 def test(self):
  with self.connect() as ftp:ftp.cwd(self.normalize_remote(self.p.remote_dir));return ftp.pwd()
 def _list(self,ftp,remote):
  try:entries=list(ftp.mlsd(remote))
  except ftplib.error_perm:
   old=ftp.pwd();out=[]
   try:
    ftp.cwd(remote)
    for raw in ftp.nlst():
     n=posixpath.basename(raw.rstrip('/'))
     if n in ('.','..'):continue
     try:ftp.cwd(posixpath.join(remote,n));typ='dir'
     except ftplib.error_perm:typ='file'
     finally:ftp.cwd(remote)
     out.append((n,typ,{}))
    return out
   finally:ftp.cwd(old)
  out=[]
  for n,f in entries:
   typ=f.get('type','file')
   if typ in ('cdir','pdir') or n in ('.','..'):continue
   if typ not in ('dir','file'):raise RuntimeError(f'Tipo FTP non supportato: {n}: {typ}')
   out.append((n,typ,f))
  return out
 def scan_all(self):
  root=self.normalize_remote(self.p.remote_dir);result={'files':[],'directories':0,'directory_paths':[],'pdf_count':0,'other_count':0};seen=set()
  with self.connect() as ftp:
   def walk(d):
    if d in seen:raise RuntimeError('Ciclo nelle directory FTP')
    seen.add(d);result['directories']+=1;result['directory_paths'].append(d);self.log.write(f'SCAN {d}')
    for n,t,f in self._list(ftp,d):
     if '/' in n or '\\' in n or any(c in n for c in ('\r','\n','\x00')):raise RuntimeError(f'Nome FTP non sicuro: {n!r}')
     child=posixpath.join(d,n)
     if t=='dir':walk(child)
     else:result['files'].append(child);result['pdf_count' if n.lower().endswith('.pdf') else 'other_count']+=1
   walk(root)
  return result
 def download_file(self,remote,local):
  local=Path(local);local.parent.mkdir(parents=True,exist_ok=True);tmp=local.with_name(local.name+'.part')
  try:
   with self.connect() as ftp:
    ftp.voidcmd('TYPE I')
    try:expected=ftp.size(remote)
    except ftplib.error_perm:expected=None
    with tmp.open('wb') as f:ftp.retrbinary('RETR '+remote,f.write,1024*1024)
   if expected is not None and tmp.stat().st_size!=expected:raise RuntimeError('Dimensione download non valida')
   tmp.replace(local);self.log.write(f'DOWNLOAD OK {remote}')
  finally:tmp.unlink(missing_ok=True)
 @staticmethod
 def _remote_hash(ftp,remote):
  digest=hashlib.sha256();ftp.retrbinary('RETR '+remote,digest.update,1024*1024);return digest.hexdigest()
 def upload_pdf_verified(self,local_pdf,remote_pdf):
  from kopia.core.integrity import sha256
  token=uuid.uuid4().hex;temp=remote_pdf+'.kopia-upload-'+token;old=remote_pdf+'.kopia-old-'+token
  expected=sha256(local_pdf);renamed=False;promoted=False
  with self.connect() as ftp:
   try:
    with Path(local_pdf).open('rb') as f:ftp.storbinary('STOR '+temp,f,1024*1024)
    if self._remote_hash(ftp,temp)!=expected:raise RuntimeError('Hash upload temporaneo non valido')
    ftp.rename(remote_pdf,old);renamed=True
    ftp.rename(temp,remote_pdf);promoted=True
    if self._remote_hash(ftp,remote_pdf)!=expected:raise RuntimeError('Hash upload finale non valido')
   except Exception:
    if renamed:
     if promoted:
      try:ftp.delete(remote_pdf)
      except ftplib.error_perm:pass
     ftp.rename(old,remote_pdf)
    raise
   finally:
    try:ftp.delete(temp)
    except ftplib.error_perm:pass
   ftp.delete(old)
  self.log.write(f'UPLOAD VERIFICATO SHA256 {remote_pdf}');return expected
 def delete_remote_file_verified(self,remote):
  self.p.validate()
  if not self.p.delete_remote_after_processing or self.p.delete_confirmation.strip()!='CANCELLA REMOTO':raise RuntimeError('Cancellazione non autorizzata')
  root=self.normalize_remote(self.p.remote_dir);target=self.normalize_remote(remote)
  if root=='/' or not target.startswith(root.rstrip('/')+'/'):raise RuntimeError('BLOCCO: root o percorso fuori root')
  with self.connect() as ftp:ftp.delete(target)
  self.log.write(f'DELETE REMOTE OK {target}')
