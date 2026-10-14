from pathlib import Path
from datetime import datetime
import zipfile, json, shutil
from kopia.core.integrity import sha256, verify_zip


class BackupService:
    """Verified full and chained incremental backups."""
    def __init__(self, logger):
        self.log = logger

    @staticmethod
    def _stamp():
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")

    @staticmethod
    def _index_path(dest: Path, slug: str, kind: str) -> Path:
        return dest / f".{slug}_{kind}_incremental_index.json"

    @staticmethod
    def _write_json_atomic(path: Path, data):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _source_manifest(source: Path):
        files = {}
        for f in sorted(source.rglob("*")):
            if f.is_file():
                rel = f.relative_to(source).as_posix()
                files[rel] = {"path": rel, "size": f.stat().st_size, "sha256": sha256(f)}
        return files

    @staticmethod
    def _manifest_list(files):
        return [files[name] for name in sorted(files)]

    def create_full(self, source: Path, dest: Path, slug: str, kind: str):
        source = source.resolve(); dest.mkdir(parents=True, exist_ok=True)
        final = dest / f"{slug}_{kind}_{self._stamp()}.zip"
        tmp = final.with_suffix(".zip.part"); tmp.unlink(missing_ok=True)
        manifest = []
        self.log.write(f"BACKUP {kind} START | source={source} | mode=full")
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for f in sorted(source.rglob("*")):
                    if f.is_dir():
                        z.write(f, f.relative_to(source).as_posix() + "/")
                    elif f.is_file():
                        rel = f.relative_to(source).as_posix()
                        manifest.append({"path": rel, "size": f.stat().st_size, "sha256": sha256(f)})
                        z.write(f, rel)
                z.writestr("_KOPIA_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            verify_zip(tmp); tmp.replace(final)
        except Exception:
            tmp.unlink(missing_ok=True); raise
        digest = sha256(final)
        self.log.write(f"BACKUP {kind} OK {final} | mode=full | file={len(manifest)} | sha256={digest}")
        return final, digest, len(manifest)

    def _latest_full_manifest(self, dest: Path, slug: str, kind: str):
        for archive in sorted(dest.glob(f"{slug}_{kind}-full_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                verify_zip(archive)
                with zipfile.ZipFile(archive, "r") as z:
                    items = json.loads(z.read("_KOPIA_MANIFEST.json"))
                return archive, {item["path"]: item for item in items}
            except Exception as exc:
                self.log.write(f"BACKUP BASE IGNORATA {archive}: {exc}")
        return None, {}

    def create_incremental(self, source: Path, dest: Path, slug: str, kind: str):
        source = source.resolve(); dest.mkdir(parents=True, exist_ok=True)
        index_path = self._index_path(dest, slug, kind); index = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                if not Path(index.get("archive", "")).is_file(): index = {}
            except Exception: index = {}
        previous_archive = Path(index["archive"]) if index else None
        previous = index.get("files", {}) if index else {}
        if not previous: previous_archive, previous = self._latest_full_manifest(dest, slug, kind)

        current = self._source_manifest(source)
        changed = [name for name in current if current[name] != previous.get(name)]
        deleted = sorted(set(previous) - set(current))
        if index and not changed and not deleted:
            archive = Path(index["archive"])
            digest = sha256(archive)
            self.log.write(f"BACKUP {kind} SKIP | mode=incremental | changed=0 | deleted=0 | archive={archive}")
            return archive, digest, 0, len(current), 0
        final = dest / f"{slug}_{kind}-incremental_{self._stamp()}.zip"
        tmp = final.with_suffix(".zip.part"); tmp.unlink(missing_ok=True)
        changed_manifest = [current[name] for name in changed]
        metadata = {
            "format": "KOPIA_INCREMENTAL_V1", "kind": kind,
            "created": datetime.now().isoformat(),
            "base_archive": str(previous_archive) if previous_archive else None,
            "previous_archive": str(previous_archive) if previous_archive else None,
            "files": self._manifest_list(current), "deleted": deleted,
        }
        self.log.write(f"BACKUP {kind} START | source={source} | mode=incremental | changed={len(changed)} | deleted={len(deleted)}")
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for name in changed: z.write(source / Path(name), name)
                z.writestr("_KOPIA_MANIFEST.json", json.dumps(changed_manifest, ensure_ascii=False, indent=2))
                z.writestr("_KOPIA_INCREMENTAL.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            verify_zip(tmp)
            with zipfile.ZipFile(tmp, "r") as z:
                loaded = json.loads(z.read("_KOPIA_INCREMENTAL.json"))
                if loaded.get("files") != self._manifest_list(current) or loaded.get("deleted") != deleted:
                    raise RuntimeError("Manifesto incrementale non valido")
            tmp.replace(final)
            self._write_json_atomic(index_path, {"version": 1, "archive": str(final), "updated": datetime.now().isoformat(), "files": current})
        except Exception:
            tmp.unlink(missing_ok=True); raise
        digest = sha256(final)
        self.log.write(f"BACKUP {kind} OK {final} | mode=incremental | changed={len(changed)} | deleted={len(deleted)} | sha256={digest}")
        return final, digest, len(changed), len(current), len(deleted)

    def secondary_copy(self, archive: Path, secondary_root: Path, kind: str):
        destdir = secondary_root / kind; destdir.mkdir(parents=True, exist_ok=True)
        dest = destdir / archive.name; tmp = dest.with_suffix(dest.suffix + ".part")
        shutil.copy2(archive, tmp)
        if sha256(tmp) != sha256(archive):
            tmp.unlink(missing_ok=True); raise RuntimeError(f"Verifica copia secondaria fallita: {archive.name}")
        tmp.replace(dest); self.log.write(f"COPIA SECONDARIA {kind} OK {dest}"); return dest

    def prune(self, dest: Path, pattern: str, keep: int):
        # Full archives are independent and may follow the configured
        # retention. Incremental members are never pruned individually.
        if "-full_" not in pattern or keep <= 0:
            return
        items = sorted(dest.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            old.unlink(missing_ok=True)
            self.log.write(f"RETENTION: rimosso {old}")
