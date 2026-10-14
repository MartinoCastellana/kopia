from pathlib import Path
import os, tempfile

def ensure_writable_directory(value: str, label: str) -> Path:
    if not value.strip():
        raise ValueError(f"{label}: percorso non configurato.")
    p = Path(value).expanduser()
    if not p.is_absolute():raise ValueError(f'{label}: usa un percorso assoluto macOS.')
    if not Path(p.anchor).exists():raise OSError(f'{label}: volume non disponibile: {p.anchor}')
    try:
        p.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".kopia-write-", dir=p)
        probe = Path(name)
        with os.fdopen(fd, "wb") as f:
            f.write(b"Kopia V3")
            f.flush()
            os.fsync(f.fileno())
        probe.unlink(missing_ok=True)
    except PermissionError as e:
        raise PermissionError(
            f"{label}: nessun permesso di scrittura su {p}. "
            "Verifica i permessi della cartella e che il volume sia montato."
        ) from e
    except OSError as e:
        raise OSError(
            f"{label}: impossibile scrivere su {p}: {e}. "
            "Controlla anche che il volume non sia montato in sola lettura."
        ) from e
    return p
