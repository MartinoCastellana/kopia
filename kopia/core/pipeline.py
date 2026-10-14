from datetime import datetime
from time import perf_counter
from pathlib import Path
import json,posixpath,tempfile,shutil
from kopia.paths import LOCK_DIR,STATE_DIR,ensure_app_dirs
from kopia.core.logging_service import Logger
from kopia.core.ftp import FTPService
from kopia.core.pdf_tiff import convert_pdf_to_tiff_600dpi,compress_pdf_300dpi,validate_pdf,validate_tiff,is_ccitt_600dpi_tiff
from kopia.core.backup import BackupService
from kopia.core.integrity import sha256

def safe_component(name):
 invalid={'/','\\','%'};out=[]
 for char in name:
  if ord(char)<32 or char in invalid or char=='%':
   out.extend(f'%{byte:02X}' for byte in char.encode('utf-8'))
  else: out.append(char)
 out=''.join(out)
 if len(out)>240:raise ValueError('Nome troppo lungo per macOS: '+name)
 return out

def migrate_legacy_local_file(previous, local, storage):
 """Move a file created by the old URL-encoded naming scheme."""
 old_value=previous.get('local') if isinstance(previous,dict) else None
 if not old_value:return
 old=Path(old_value);new=Path(local);originals=(Path(storage)/'originals').resolve()
 try:old_resolved=old.resolve();old_rel=old_resolved.relative_to(originals)
 except (OSError,ValueError):return
 if old_resolved==new.resolve() or not old_resolved.is_file() or new.exists():return
 new.parent.mkdir(parents=True,exist_ok=True);old_resolved.replace(new)
 old_tiff=Path(storage)/'tiff'/old_rel.parent/(old_rel.name+'.tiff')
 new_rel=new.resolve().relative_to(originals)
 new_tiff=Path(storage)/'tiff'/new_rel.parent/(new_rel.name+'.tiff')
 if old_tiff.is_file() and not new_tiff.exists():
  new_tiff.parent.mkdir(parents=True,exist_ok=True);old_tiff.replace(new_tiff)
 for directory in (old_resolved.parent,old_tiff.parent):
  while directory != directory.parent and directory.exists() and not any(directory.iterdir()):
   directory.rmdir();directory=directory.parent
class Pipeline:
 def __init__(self,p):self.p=p
 def _write_history(self,path,report):
  path.parent.mkdir(parents=True,exist_ok=True);pending=path.with_suffix('.tmp');pending.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(path)
 def _status(self,mode,data):
  target=STATE_DIR/f'{self.p.slug}_{mode}_status.json';pending=target.with_suffix('.tmp');pending.write_text(json.dumps({**data,'updated':datetime.now().isoformat()},ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(target)
 def _timing(self,timings,name,started):
  entry=timings[name];entry['seconds']=round(entry['seconds']+(perf_counter()-started),3);entry['count']+=1
 def _backup(self,b,kind):
  dest=Path(self.p.daily_backup_dir if kind=='daily' else self.p.weekly_backup_dir)
  a,d,changed,total,deleted=b.create_incremental(Path(self.p.storage_dir),dest,self.p.slug,kind);sec=None
  if self.p.secondary_backup_enabled and self.p.secondary_backup_dir.strip():
   sec=b.secondary_copy(a,Path(self.p.secondary_backup_dir),kind)
  return {'archive':str(a),'sha256':d,'changed_files':changed,'total_files':total,'deleted_files':deleted,'mode':'incremental','secondary':str(sec) if sec else None}
 def run(self,mode='daily'):
  if mode not in ('daily','weekly'):raise ValueError('ModalitÃ  non valida')
  self.p.ensure_dirs();ensure_app_dirs()
  import fcntl
  lock=(LOCK_DIR/(self.p.slug+'.lock')).open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
  try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:lock.close();raise RuntimeError('Ciclo giÃ  in esecuzione')
  started=datetime.now();log=Logger(self.p.name,Path(self.p.log_dir)/f'{self.p.slug}_{mode}_{started:%Y-%m-%d_%H-%M-%S-%f}.log')
  report={'run_id':started.strftime('%Y%m%d_%H%M%S_%f'),'started':started.isoformat(),'mode':mode,'phase':'transfer','status':'running','processed':[],'errors':[],'transfer':{'total':0,'completed':0},'conversion':{'total':0,'completed':0},'timings':{key:{'seconds':0.0,'count':0} for key in ('scan','download','compression','upload','tiff_conversion','backup')}};statefile=STATE_DIR/(self.p.slug+'_files.json');history_path=STATE_DIR/'history'/f'{self.p.slug}_{mode}_{report["run_id"]}.json';self._write_history(history_path,report)
  try:
   state=json.loads(statefile.read_text(encoding='utf-8')) if statefile.exists() else {}
   log.write('START '+mode+' · FASE TRASFERIMENTO');backup=BackupService(log);conversion_queue=[];self._status(mode,{'status':'running','phase':'transfer','mode':mode,'started':report['started'],'transfer':report['transfer'],'conversion':report['conversion'],'timings':report['timings'],'errors':[]})
   if mode=='daily':
    ftp=FTPService(self.p,log);step_started=perf_counter()
    try:scan=ftp.scan_all()
    finally:self._timing(report['timings'],'scan',step_started)
    report['scan']=scan;report['transfer']['total']=len(scan['files']);storage=Path(self.p.storage_dir);rr=ftp.normalize_remote(self.p.remote_dir)
    def relative(remote):
     rel=posixpath.relpath(remote,rr)
     if rel=='..' or rel.startswith('../'):raise RuntimeError('Percorso fuori root')
     return Path(*[safe_component(x) for x in rel.split('/') if x!='.'])
    for remote in scan['directory_paths']:(storage/'originals'/relative(remote)).mkdir(parents=True,exist_ok=True)
    for remote in scan['files']:
     item={'remote':remote};report['processed'].append(item)
     try:
      rel=relative(remote);local=storage/'originals'/rel;previous=state.get(remote,{})
      migrate_legacy_local_file(previous,local,storage)
      with tempfile.TemporaryDirectory(prefix='kopia-') as tmpdir:
       incoming=Path(tmpdir)/'incoming';step_started=perf_counter()
       try:ftp.download_file(remote,incoming)
       finally:self._timing(report['timings'],'download',step_started)
       incoming_hash=sha256(incoming)
       if remote.lower().endswith('.pdf'):validate_pdf(incoming)
       server_hash=previous.get('server_hash',previous.get('remote_hash'));source_hash=previous.get('source_hash')
       local_hash=sha256(local) if local.exists() else None
       if local.exists() and previous.get('original_hash') and local_hash!=previous.get('original_hash'):
        raise RuntimeError('BLOCCO SICUREZZA: originale locale diverso dallo stato registrato; conservato senza sostituzione')
       if local.exists() and not previous.get('original_hash') and local_hash!=incoming_hash:
        raise RuntimeError('BLOCCO SICUREZZA: originale locale presente ma senza stato verificabile; conservato senza sostituzione')
       unchanged=local.exists() and (incoming_hash in {server_hash,source_hash} or incoming_hash==local_hash) and (not previous.get('original_hash') or previous.get('original_hash')==local_hash)
       if not unchanged:
        if local.exists() and sha256(local)!=incoming_hash:
         version=storage/'versions'/rel.parent/(rel.name+'.'+datetime.now().strftime('%Y%m%d%H%M%S%f'));version.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(local,version)
        local.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.kopia-',dir=local.parent) as staging:
         atomic=Path(staging)/'download';shutil.copy2(incoming,atomic);atomic.replace(local)
       if not unchanged and sha256(local)!=incoming_hash:raise RuntimeError("Verifica SHA256 dell'originale locale fallita")
       effective_source_hash=source_hash if unchanged else incoming_hash;item['local']=str(local);item['original_sha256']=sha256(local);remote_hash=server_hash or incoming_hash
       if remote.lower().endswith('.pdf'):
        validate_pdf(local);tiff=storage/'tiff'/rel.parent/(rel.name+'.tiff');tiff.parent.mkdir(parents=True,exist_ok=True);conversion_queue.append((remote,local,tiff,item))
        if not unchanged:
         compressed=Path(tmpdir)/'compressed-color-300dpi.pdf';step_started=perf_counter()
         try:compress_pdf_300dpi(local,compressed)
         finally:self._timing(report['timings'],'compression',step_started)
         step_started=perf_counter()
         try:remote_hash=ftp.upload_pdf_verified(compressed,remote)
         finally:self._timing(report['timings'],'upload',step_started)
         compressed.unlink();item['server_sha256']=remote_hash
        log.write(f'ORIGINALE VERIFICATO SHA256 {incoming_hash} E CONSERVATO {local}; PDF SERVER RGB 300 DPI {remote}')
       state[remote]={'source_hash':effective_source_hash,'server_hash':remote_hash,'original_hash':sha256(local),'local':str(local)}
       pending=statefile.with_suffix('.tmp');pending.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(statefile)
       # Remote deletion is intentionally disabled by policy.  A verified
       # download is never a reason to remove the source from the server;
       # this also protects the remote originals if a later step fails.
       item['remote_deleted']=False
       if self.p.delete_remote_after_processing:
        log.write(f'BLOCCO SICUREZZA: cancellazione remota ignorata {remote}')
       item['status']='success';report['transfer']['completed']+=1;self._status(mode,{'status':'running','phase':'transfer','mode':mode,'started':report['started'],'transfer':report['transfer'],'conversion':report['conversion'],'timings':report['timings'],'current':remote,'errors':report['errors']})
     except Exception as e:
       item.update(status='failed',error=str(e));report['errors'].append(f'{remote}: {e}');log.write(f'ERRORE {remote}: {e}; controlla lo stato remoto');self._status(mode,{'status':'running','phase':'transfer','mode':mode,'started':report['started'],'transfer':report['transfer'],'conversion':report['conversion'],'timings':report['timings'],'current':remote,'errors':report['errors']})
   report['conversion']['total']=len(conversion_queue);report['phase']='conversion';log.write('TRASFERIMENTO COMPLETATO · INIZIO CONVERSIONE TIFF CCITT GROUP 4 600 DPI');self._status(mode,{'status':'running','phase':'conversion','mode':mode,'started':report['started'],'transfer':report['transfer'],'conversion':report['conversion'],'timings':report['timings'],'errors':report['errors']})
   for remote,local,tiff,item in conversion_queue:
    try:
     step_started=perf_counter()
     try:
      if not is_ccitt_600dpi_tiff(tiff):convert_pdf_to_tiff_600dpi(local,tiff)
     finally:self._timing(report['timings'],'tiff_conversion',step_started)
     validate_tiff(tiff);item['local_tiff']=str(tiff);item['tiff_status']='success';report['conversion']['completed']+=1;log.write(f'TIFF CCITT GROUP 4 600 DPI VERIFICATO {tiff}')
    except Exception as e:
     item['tiff_status']='failed';item['tiff_error']=str(e);report['errors'].append(f'{remote} TIFF: {e}');log.write(f'ERRORE CONVERSIONE TIFF {remote}: {e}')
    self._status(mode,{'status':'running','phase':'conversion','mode':mode,'started':report['started'],'transfer':report['transfer'],'conversion':report['conversion'],'timings':report['timings'],'current':remote,'errors':report['errors']})
   step_started=perf_counter()
   try:report['backup']=self._backup(backup,mode)
   finally:self._timing(report['timings'],'backup',step_started)
   report['status']='partial_failure' if report['errors'] else 'success'
   log.write('FINE '+report['status']);return 2 if report['errors'] else 0
  except Exception as e:
   report['status']='failed';report['errors'].append(str(e));log.write('ERRORE CICLO '+str(e));return 1
  finally:
   try:
     report['finished']=datetime.now().isoformat();self._write_history(history_path,report);target=STATE_DIR/f'{self.p.slug}_{mode}_last.json';pending=target.with_suffix('.tmp');pending.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(target);self._status(mode,{'status':report.get('status','failed'),'phase':'complete','mode':mode,'started':report.get('started'),'finished':report['finished'],'transfer':report.get('transfer',{}),'conversion':report.get('conversion',{}),'timings':report.get('timings',{}),'errors':report.get('errors',[])})
   finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()
