from datetime import datetime
from pathlib import Path
from kopia.paths import GENERAL_LOG, ensure_app_dirs

class Logger:
    def __init__(self, project_name: str, cycle_file: Path):
        ensure_app_dirs()
        self.project_name = project_name
        self.cycle_file = cycle_file
        cycle_file.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str):
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{self.project_name}] {message}"
        if __import__('sys').stdout is not None:print(line,flush=True)
        for path in (self.cycle_file, GENERAL_LOG):
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
