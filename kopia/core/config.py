import json
from kopia.paths import CONFIG_FILE, ensure_app_dirs
from kopia.models.project import Project

def load_projects():
    ensure_app_dirs()
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return [Project.from_dict(x) for x in data]
    except Exception as e:
        raise RuntimeError(f"Configurazione illeggibile: {CONFIG_FILE}: {e}") from e

def save_projects(projects):
    ensure_app_dirs()
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([p.to_dict() for p in projects], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)

def get_project(slug):
    for p in load_projects():
        if p.slug == slug:
            return p
    raise KeyError(f"Progetto non trovato: {slug}")
