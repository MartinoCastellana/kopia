import sys
from kopia.core.config import get_project
from kopia.core.pipeline import Pipeline

if len(sys.argv) != 3:
    raise SystemExit("Uso: runner.py <slug> <daily|weekly>")
p=get_project(sys.argv[1])
raise SystemExit(Pipeline(p).run(sys.argv[2]))
