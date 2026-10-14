from pathlib import Path
import os
_default_data = Path.home()/'Library'/'Application Support'/'Kopia'
APP_DATA=Path(os.environ.get('KOPIA_DATA',str(_default_data)))
CONFIG_FILE=APP_DATA/'projects.json'
GENERAL_LOG=APP_DATA/'general.log'
LOCK_DIR=APP_DATA/'locks'
STATE_DIR=APP_DATA/'state'
def ensure_app_dirs():
 for p in (APP_DATA,LOCK_DIR,STATE_DIR):p.mkdir(parents=True,exist_ok=True)
