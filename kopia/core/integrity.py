from pathlib import Path
import hashlib, zipfile, json

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_zip(path: Path):
    with zipfile.ZipFile(path, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"ZIP corrotto: {bad}")

        manifest=json.loads(z.read('_KOPIA_MANIFEST.json'))
        for item in manifest:
            h=hashlib.sha256();size=0
            with z.open(item['path']) as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):
                    h.update(chunk);size+=len(chunk)
            if h.hexdigest()!=item['sha256'] or size!=item['size']:
                raise RuntimeError('Manifesto ZIP non valido: '+item['path'])
