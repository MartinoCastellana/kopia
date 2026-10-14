import os
import plistlib
import subprocess
import sys
from pathlib import Path

from kopia.paths import APP_DATA, ensure_app_dirs


class MacScheduler:
    """Installa automazioni per l'utente corrente tramite launchd."""

    def __init__(self, runner):
        self.runner = Path(runner).resolve()
        self.agent_dir = Path.home() / "Library" / "LaunchAgents"

    def _label(self, slug, kind):
        return f"com.kopia.{slug}.{kind}"

    def _path(self, slug, kind):
        return self.agent_dir / f"{self._label(slug, kind)}.plist"

    def _unload(self, path):
        if path.exists():
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], capture_output=True, text=True)

    def remove_project(self, slug):
        for kind in ("daily", "weekly"):
            path = self._path(slug, kind)
            self._unload(path)
            path.unlink(missing_ok=True)

    def install_project(self, project):
        project.validate()
        ensure_app_dirs()
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        for kind in ("daily", "weekly"):
            path = self._path(project.slug, kind)
            self._unload(path)
            if not getattr(project, f"{kind}_enabled"):
                path.unlink(missing_ok=True)
                continue
            arguments = ["--run", project.slug, kind] if getattr(sys, "frozen", False) else [str(self.runner), project.slug, kind]
            interval = {"Hour": int(getattr(project, f"{kind}_hour")), "Minute": int(getattr(project, f"{kind}_minute"))}
            if kind == "weekly":
                interval["Weekday"] = (int(project.weekly_day) + 1) % 7
            payload = {
                "Label": self._label(project.slug, kind),
                "ProgramArguments": [sys.executable, *arguments],
                "WorkingDirectory": str(self.runner.parent),
                "StartCalendarInterval": interval,
                "ProcessType": "Background",
                "StandardOutPath": str(APP_DATA / f"{project.slug}-{kind}.log"),
                "StandardErrorPath": str(APP_DATA / f"{project.slug}-{kind}.error.log"),
            }
            with path.open("wb") as handle:
                plistlib.dump(payload, handle, sort_keys=False)
            result = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], capture_output=True, text=True)
            if result.returncode:
                path.unlink(missing_ok=True)
                raise RuntimeError(result.stderr.strip() or "Impossibile registrare l'automazione macOS.")


def scheduler_for(runner):
    return MacScheduler(runner)
