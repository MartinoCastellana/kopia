from dataclasses import dataclass, asdict
from kopia.core.storage_access import ensure_writable_directory

@dataclass
class Project:
    name: str = ""
    host: str = ""
    port: int = 21
    username: str = ""
    password: str = ""
    remote_dir: str = "/"
    storage_dir: str = ""
    daily_backup_dir: str = ""
    weekly_backup_dir: str = ""
    secondary_backup_dir: str = ""
    secondary_backup_enabled: bool = False
    log_dir: str = ""
    use_ftps: bool = True
    verify_tls: bool = True
    passive: bool = True
    timeout: int = 60
    delete_remote_tiff: bool = False
    confirmation: str = ""
    delete_remote_after_processing: bool = False
    delete_confirmation: str = ""
    daily_enabled: bool = True
    daily_hour: int = 0
    daily_minute: int = 0
    weekly_enabled: bool = True
    weekly_day: int = 5
    weekly_hour: int = 3
    weekly_minute: int = 0
    daily_keep: int = 30
    weekly_keep: int = 12

    @property
    def slug(self):
        import re
        s = re.sub(r"[^A-Za-z0-9._-]+", "-", self.name.strip()).strip("-")
        if s.lower().split('.')[0] in {'con','prn','aux','nul',*[f'com{i}' for i in range(1,10)],*[f'lpt{i}' for i in range(1,10)]}:s='project-'+s
        return s if s not in ("",".","..") else "project"

    def validate(self):
        if not self.name.strip(): raise ValueError("Nome progetto obbligatorio.")
        if len(self.slug)>80:raise ValueError("Nome progetto troppo lungo (massimo 80 caratteri normalizzati).")
        if not self.host.strip(): raise ValueError("Server FTP obbligatorio.")
        if not (1 <= int(self.port) <= 65535): raise ValueError("Porta FTP non valida.")
        if not self.username.strip(): raise ValueError("Username FTP obbligatorio.")
        for label, value in (
            ("Storage", self.storage_dir),
            ("Backup giornalieri", self.daily_backup_dir),
            ("Backup settimanali", self.weekly_backup_dir),
            ("Log", self.log_dir),
        ):
            if not value.strip(): raise ValueError(f"{label}: percorso obbligatorio.")

        from pathlib import Path
        from kopia.core.ftp import FTPService
        for key,maximum in [('daily_hour',23),('weekly_hour',23),('daily_minute',59),('weekly_minute',59),('weekly_day',6)]:
            if not 0<=int(getattr(self,key))<=maximum:raise ValueError(f'{key}: valore non valido')
        if self.daily_keep<1 or self.weekly_keep<1:raise ValueError('Retention minima: 1 backup.')
        if self.secondary_backup_enabled and not self.secondary_backup_dir.strip():raise ValueError('Per attivare la copia secondaria indicare una cartella.')
        storage=Path(self.storage_dir).resolve()
        paths=[Path(v).resolve() for v in (self.daily_backup_dir,self.weekly_backup_dir,self.log_dir,self.secondary_backup_dir) if v.strip()]
        for i,a in enumerate(paths):
            for b in paths[i+1:]:
                if a==b or a in b.parents or b in a.parents:raise ValueError('Backup, copia secondaria e log devono usare cartelle separate senza annidamento.')
        for path in paths:
            if path==storage or storage in path.parents or path in storage.parents:raise ValueError('Storage e cartelle backup/log devono essere separati, senza annidamento.')
        if Path(self.daily_backup_dir).resolve()==Path(self.weekly_backup_dir).resolve():raise ValueError('Backup daily e weekly devono usare cartelle diverse.')
        FTPService.normalize_remote(self.remote_dir)
        if self.delete_remote_after_processing:
            if FTPService.normalize_remote(self.remote_dir) == "/":
                raise ValueError("La root FTP '/' non puÃƒÂ² essere usata per cancellazioni.")
            if self.delete_confirmation.strip() != "CANCELLA REMOTO":
                raise ValueError('Per abilitare la cancellazione scrivere esattamente "CANCELLA REMOTO".')

    def ensure_dirs(self):
        self.validate()
        ensure_writable_directory(self.storage_dir, "Storage cumulativo")
        ensure_writable_directory(self.daily_backup_dir, "Backup giornalieri")
        ensure_writable_directory(self.weekly_backup_dir, "Backup settimanali")
        ensure_writable_directory(self.log_dir, "Log")
        if self.secondary_backup_dir.strip():
            ensure_writable_directory(self.secondary_backup_dir, "Copia secondaria")

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # migration compatibility from the simplified V3 backup_dir
        data = dict(data)
        if "secondary_backup_enabled" not in data:
            data["secondary_backup_enabled"] = bool(str(data.get("secondary_backup_dir", "")).strip())
        legacy = data.get("backup_dir", "")
        if legacy:
            data.setdefault("daily_backup_dir", str(__import__("pathlib").Path(legacy)/"daily"))
            data.setdefault("weekly_backup_dir", str(__import__("pathlib").Path(legacy)/"weekly"))
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k:v for k,v in data.items() if k in allowed})
