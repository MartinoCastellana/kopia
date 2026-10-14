import os,sys
from kopia.paths import ensure_app_dirs,APP_DATA
def _configure_tk_runtime():
 if not getattr(sys,'frozen',False): return
 bundle=getattr(sys,'_MEIPASS','')
 if bundle:
  sys.path.insert(0,os.path.join(bundle,'pystdlib'))
  os.environ['TCL_LIBRARY']=os.path.join(bundle,'tcl','tcl8.6')
  os.environ['TK_LIBRARY']=os.path.join(bundle,'tcl','tk8.6')
def main():
 ensure_app_dirs()
 if len(sys.argv)>1:
  if len(sys.argv)!=4 or sys.argv[1]!='--run':raise ValueError('Uso: Kopia --run <slug> <daily|weekly>')
  from kopia.core.config import get_project
  from kopia.core.pipeline import Pipeline
  return Pipeline(get_project(sys.argv[2])).run(sys.argv[3])
 _configure_tk_runtime()
 from kopia.gui.app import run
 run();return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception:
  import traceback
  ensure_app_dirs();(APP_DATA/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
  raise SystemExit(1)
