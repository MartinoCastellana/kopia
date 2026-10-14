from __future__ import annotations

import threading
import importlib
from pathlib import Path
tk = importlib.import_module("kopia.gui.tkinter")
filedialog = importlib.import_module("kopia.gui.tkinter.filedialog")
messagebox = importlib.import_module("kopia.gui.tkinter.messagebox")
ttk = importlib.import_module("kopia.gui.tkinter.ttk")

from kopia.core.config import load_projects, save_projects
from kopia.core.ftp import FTPService
from kopia.core.pipeline import Pipeline
from kopia.core.scheduler import scheduler_for
from kopia.models.project import Project
from kopia import __version__


BG = "#0f172a"
PANEL = "#172238"
PANEL_2 = "#1e2d46"
TEXT = "#e7eef8"
MUTED = "#91a4bd"
ACCENT = "#5eead4"
ACCENT_DARK = "#123a40"
DANGER = "#fb7185"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Kopia · v{__version__}")
        self.geometry("1180x760")
        self.minsize(1020, 680)
        self.configure(bg=BG)
        self.projects = load_projects()
        self.current: Project | None = None
        self.vars: dict[str, tk.Variable] = {}
        self._build_style()
        self._build_shell()
        self._show_dashboard()

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Card.TFrame", background=PANEL_2)
        self.ui_font = "SF Pro Display"
        self.ui_semibold = "SF Pro Display"
        style.configure("TLabel", background=BG, foreground=TEXT, font=(self.ui_font, 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(self.ui_font, 9))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=(self.ui_font, 10))
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=(self.ui_font, 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=(self.ui_semibold, 25))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=(self.ui_semibold, 13))
        style.configure("Stat.TLabel", background=PANEL_2, foreground=TEXT, font=(self.ui_semibold, 21))
        style.configure("StatCaption.TLabel", background=PANEL_2, foreground=MUTED, font=(self.ui_font, 9))
        style.configure("TButton", background=PANEL_2, foreground=TEXT, borderwidth=0, padding=(14, 9), font=(self.ui_font, 10))
        style.map("TButton", background=[("active", "#2c4160")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#092629", padding=(16, 10), font=(self.ui_semibold, 10))
        style.map("Accent.TButton", background=[("active", "#8bf5e5")])
        style.configure("Danger.TButton", background="#482334", foreground="#ffdce2", padding=(12, 8))
        style.configure("TEntry", fieldbackground="#0d1628", foreground=TEXT, insertcolor=TEXT, borderwidth=0, padding=8)
        style.configure("TCombobox", fieldbackground="#0d1628", foreground=TEXT, selectbackground="#2c4160", padding=6)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=(self.ui_font, 10))
        style.map("TCheckbutton", background=[("active", PANEL)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=42, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", font=(self.ui_semibold, 9))
        style.map("Treeview", background=[("selected", "#28505a")], foreground=[("selected", "#ffffff")])
        style.configure("Horizontal.TProgressbar", troughcolor="#0d1628", background=ACCENT, borderwidth=0)

    def _build_shell(self):
        self.sidebar = ttk.Frame(self, style="Panel.TFrame", width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand = ttk.Frame(self.sidebar, style="Panel.TFrame")
        brand.pack(fill="x", padx=22, pady=(28, 34))
        tk.Label(brand, text="K", bg=ACCENT, fg="#092629", font=(self.ui_semibold, 17), width=4, height=2).pack(side="left")
        tk.Label(brand, text=f"Kopia\nmacOS · v{__version__}", bg=PANEL, fg=TEXT, justify="left", font=(self.ui_semibold, 11)).pack(side="left", padx=10)
        self.nav = {}
        for key, label in (("dashboard", "⌂   Panoramica"), ("projects", "▦   Progetti"), ("schedule", "◷   Automazioni"), ("help", "?   Guida")):
            b = tk.Button(self.sidebar, text=label, anchor="w", relief="flat", borderwidth=0, bg=PANEL, fg=MUTED, activebackground=PANEL_2, activeforeground=TEXT, font=(self.ui_font, 11), padx=22, pady=13, command=lambda k=key: self._navigate(k))
            b.pack(fill="x")
            self.nav[key] = b
        tk.Label(self.sidebar, text="", bg=PANEL).pack(expand=True)
        tk.Label(self.sidebar, text="Protezione dati\nFTP / FTPS • Backup verificati", bg=PANEL, fg=MUTED, justify="left", anchor="w", font=(self.ui_font, 9), padx=22, pady=18).pack(fill="x")
        self.main = ttk.Frame(self, padding=(34, 28, 34, 24))
        self.main.pack(side="left", fill="both", expand=True)

    def _clear(self):
        for child in self.main.winfo_children(): child.destroy()

    def _navigate(self, key):
        if key == "dashboard": self._show_dashboard()
        elif key == "projects": self._show_projects()
        elif key == "schedule": self._show_schedule()
        else: self._show_help()

    def _active_nav(self, key):
        for k, button in self.nav.items():
            button.configure(bg=PANEL_2 if k == key else PANEL, fg=TEXT if k == key else MUTED)

    def _header(self, eyebrow, title, subtitle=""):
        top = ttk.Frame(self.main)
        top.pack(fill="x", pady=(0, 22))
        ttk.Label(top, text=eyebrow.upper(), style="Muted.TLabel").pack(anchor="w")
        ttk.Label(top, text=title, style="Title.TLabel").pack(anchor="w", pady=(3, 4))
        if subtitle: ttk.Label(top, text=subtitle, style="Muted.TLabel").pack(anchor="w")
        return top

    def _stat_card(self, parent, value, caption):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(18, 14))
        card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ttk.Label(card, text=value, style="Stat.TLabel").pack(anchor="w")
        ttk.Label(card, text=caption, style="StatCaption.TLabel").pack(anchor="w", pady=(3, 0))
        return card

    def _show_dashboard(self):
        self._clear(); self._active_nav("dashboard")
        self._header("Workspace", "Panoramica", "Tutto quello che serve per controllare trasferimenti, backup e automazioni.")
        stats = ttk.Frame(self.main); stats.pack(fill="x", pady=(0, 24))
        active = sum(1 for p in self.projects if p.daily_enabled or p.weekly_enabled)
        self._stat_card(stats, str(len(self.projects)), "progetti configurati")
        self._stat_card(stats, str(active), "con automazioni attive")
        self._stat_card(stats, str(sum(1 for p in self.projects if p.use_ftps)), "connessioni protette FTPS")
        content = ttk.Frame(self.main); content.pack(fill="both", expand=True)
        welcome = ttk.Frame(content, style="Panel.TFrame", padding=24); welcome.pack(side="left", fill="both", expand=True)
        ttk.Label(welcome, text="Inizia da qui", style="Section.TLabel").pack(anchor="w")
        ttk.Label(welcome, text="Configura un progetto FTP, verifica la connessione e poi attiva i cicli automatici.", style="PanelMuted.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(7, 22))
        for number, title, detail in (("01", "Crea un progetto", "Inserisci server, credenziali e cartelle locali separate."), ("02", "Verifica prima di partire", "Controlla la connessione e usa inizialmente la cancellazione remota disattivata."), ("03", "Attiva le automazioni", "Scegli gli orari daily e weekly dalla sezione Automazioni.")):
            row = ttk.Frame(welcome, style="Card.TFrame", padding=14); row.pack(fill="x", pady=4)
            tk.Label(row, text=number, bg=ACCENT, fg="#092629", font=(self.ui_semibold, 10), width=4, pady=5).pack(side="left")
            copy = ttk.Frame(row, style="Card.TFrame"); copy.pack(side="left", padx=14)
            ttk.Label(copy, text=title, style="Panel.TLabel").pack(anchor="w")
            ttk.Label(copy, text=detail, style="PanelMuted.TLabel", wraplength=420).pack(anchor="w", pady=(3, 0))
        ttk.Button(welcome, text="＋  Crea il primo progetto", style="Accent.TButton", command=self._new_project).pack(anchor="w", pady=(22, 0))
        recent = ttk.Frame(content, style="Card.TFrame", padding=22); recent.pack(side="right", fill="y", padx=(20, 0)); recent.configure(width=280); recent.pack_propagate(False)
        ttk.Label(recent, text="I tuoi progetti", style="Section.TLabel").pack(anchor="w", pady=(0, 14))
        if not self.projects:
            ttk.Label(recent, text="Nessun progetto ancora.\nCreane uno per iniziare.", style="PanelMuted.TLabel", justify="left").pack(anchor="w")
        else:
            for project in self.projects[:6]:
                item = ttk.Frame(recent, style="Panel.TFrame", padding=(0, 8)); item.pack(fill="x")
                status, _ = self._project_status(project.slug)
                ttk.Label(item, text=project.name or "Progetto senza nome", style="Panel.TLabel").pack(anchor="w")
                ttk.Label(item, text=status, style="PanelMuted.TLabel").pack(anchor="w", pady=(2, 0))
            ttk.Button(recent, text="Vedi tutti i progetti", command=self._show_projects).pack(fill="x", pady=(18, 0))

    def _show_projects(self):
        self._clear(); self._active_nav("projects")
        head = self._header("Workspace", "I tuoi progetti", "Gestisci connessioni, backup e cicli di sincronizzazione da un unico punto.")
        ttk.Button(head, text="＋  Nuovo progetto", style="Accent.TButton", command=self._new_project).pack(side="right", anchor="n")
        body = ttk.Frame(self.main); body.pack(fill="both", expand=True)
        left = ttk.Frame(body); left.pack(side="left", fill="both", expand=True)
        tree = ttk.Treeview(left, columns=("host", "remote", "mode", "status", "progress"), show="headings", selectmode="browse")
        tree.heading("host", text="PROGETTO / SERVER"); tree.heading("remote", text="CARTELLA REMOTA"); tree.heading("mode", text="PROTOCOLLO"); tree.heading("status", text="STATO"); tree.heading("progress", text="AVANZAMENTO")
        tree.column("host", width=270, anchor="w"); tree.column("remote", width=210, anchor="w"); tree.column("mode", width=90, anchor="w"); tree.column("status", width=120, anchor="w"); tree.column("progress", width=125, anchor="w")
        tree.pack(fill="both", expand=True)
        for p in self.projects:
            status,progress=self._project_status(p.slug);tree.insert("", "end", iid=p.slug, values=(f"{p.name}\n{p.host}:{p.port}", p.remote_dir, "FTPS" if p.use_ftps else "FTP", status, progress))
        self._refresh_project_status(tree)
        empty = ttk.Label(left, text="Nessun progetto configurato. Crea il primo per iniziare.", style="Muted.TLabel")
        if not self.projects: empty.place(relx=.5, rely=.5, anchor="center")
        right = ttk.Frame(body, style="Card.TFrame", padding=22); right.pack(side="right", fill="y", padx=(24, 0)); right.configure(width=265); right.pack_propagate(False)
        ttk.Label(right, text="Azioni progetto", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(right, text="Seleziona una riga a sinistra. Le azioni principali sono qui.", style="PanelMuted.TLabel", wraplength=215).pack(anchor="w", pady=(0, 18))
        ttk.Label(right, text="ESECUZIONE", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Button(right, text="▶  Avvia ciclo daily", style="Accent.TButton", command=lambda: self._run_selected(tree, "daily")).pack(fill="x", pady=3)
        ttk.Button(right, text="◉  Avvia ciclo weekly", command=lambda: self._run_selected(tree, "weekly")).pack(fill="x", pady=3)
        ttk.Label(right, text="RISULTATI", style="PanelMuted.TLabel").pack(anchor="w", pady=(16, 4))
        ttk.Button(right, text="Dettagli ultimo ciclo", command=lambda: self._show_last_cycle(tree)).pack(fill="x", pady=3)
        ttk.Button(right, text="Storico cicli", command=lambda: self._show_cycle_history(tree)).pack(fill="x", pady=3)
        ttk.Label(right, text="CONFIGURAZIONE", style="PanelMuted.TLabel").pack(anchor="w", pady=(16, 4))
        ttk.Button(right, text="Modifica progetto", command=lambda: self._edit_selected(tree)).pack(fill="x", pady=3)
        ttk.Button(right, text="Verifica connessione", command=lambda: self._test_selected(tree)).pack(fill="x", pady=3)
        ttk.Button(right, text="Elimina progetto", style="Danger.TButton", command=lambda: self._delete_selected(tree)).pack(fill="x", pady=(18, 3))
        tree.bind("<Double-1>", lambda e: self._edit_selected(tree))

    def _selected(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showinfo("Selezione necessaria", "Seleziona prima un progetto."); return None
        return next((p for p in self.projects if p.slug == selected[0]), None)

    def _show_last_cycle(self, tree):
        project=self._selected(tree)
        if not project:return
        from kopia.paths import STATE_DIR
        import json
        reports=[]
        for mode in ("daily","weekly"):
            path=STATE_DIR/f"{project.slug}_{mode}_last.json"
            if path.exists():
                try: reports.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError,ValueError): pass
        if not reports:
            messagebox.showinfo("Dettagli ciclo", "Non è ancora disponibile un report per questo progetto."); return
        report=max(reports,key=lambda x:x.get("finished",x.get("started",""))); lines=[f"Progetto: {project.name}",f"Modalità: {report.get('mode','—')}",f"Stato: {report.get('status','—')}",""]
        labels={"scan":"Scansione","download":"Download","compression":"Compressione","upload":"Upload","tiff_conversion":"Conversione TIFF","backup":"Creazione backup"}
        for key,label in labels.items():
            timing=report.get("timings",{}).get(key,{})
            lines.append(f"{label}: {float(timing.get('seconds',0)):.3f} s ({int(timing.get('count',0))} operazioni)")
        lines += ["",f"File trasferiti: {report.get('transfer',{}).get('completed',0)}/{report.get('transfer',{}).get('total',0)}",f"TIFF convertiti: {report.get('conversion',{}).get('completed',0)}/{report.get('conversion',{}).get('total',0)}"]
        if report.get("errors"): lines += ["",f"Errori: {len(report['errors'])}"]
        messagebox.showinfo("Dettagli ultimo ciclo", "\n".join(lines))

    def _show_cycle_history(self, tree):
        project=self._selected(tree)
        if not project:return
        from kopia.paths import STATE_DIR
        import json
        records=[]
        for path in STATE_DIR.glob(f"history/{project.slug}_*.json"):
            try: records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError,ValueError): pass
        records.sort(key=lambda x:x.get("started", ""), reverse=True)
        if not records:
            messagebox.showinfo("Storico cicli", "Non è ancora disponibile alcuno storico per questo progetto."); return
        lines=[f"Storico · {project.name}",""]
        for report in records[:30]:
            timing=report.get("timings",{}); total=sum(float(v.get("seconds",0)) for v in timing.values()); transfer=report.get("transfer",{}); conversion=report.get("conversion",{})
            started=report.get("started", "—")[:19].replace("T", " "); finished=report.get("finished", "in corso")[:19].replace("T", " ") if report.get("finished") else "in corso"
            lines.append(f"{started} → {finished} | {report.get('mode','—')} | {report.get('status','—')} | {total:.1f}s | trasferiti {transfer.get('completed',0)}/{transfer.get('total',0)} | TIFF {conversion.get('completed',0)}/{conversion.get('total',0)}")
        if len(records)>30: lines.append(f"… altri {len(records)-30} cicli conservati nei report JSON")
        messagebox.showinfo("Storico cicli", "\n".join(lines))

    def _project_status(self, slug):
        from kopia.paths import STATE_DIR
        import json
        candidates=sorted(STATE_DIR.glob(f"{slug}_*_status.json"), key=lambda x:x.stat().st_mtime, reverse=True)
        if not candidates:return "Nessun ciclo", "—"
        try:
            data=json.loads(candidates[0].read_text(encoding="utf-8")); phase=data.get("phase", "—"); status=data.get("status", "—"); transfer=data.get("transfer",{}); conversion=data.get("conversion",{})
            if phase=="transfer": progress=f"{transfer.get('completed',0)}/{transfer.get('total',0)} trasferiti"
            elif phase=="conversion": progress=f"{conversion.get('completed',0)}/{conversion.get('total',0)} TIFF"
            else: progress=(data.get("finished", "") or "")[:19].replace("T", " ") or "completato"
            return f"{status} · {phase}", progress
        except (OSError,ValueError):return "Stato non leggibile", "—"

    def _refresh_project_status(self, tree):
        if not tree.winfo_exists(): return
        for p in self.projects:
            if tree.exists(p.slug):
                status,progress=self._project_status(p.slug);values=list(tree.item(p.slug,"values"));values[-2:]=[status,progress];tree.item(p.slug,values=values)
        self.after(2000, lambda: self._refresh_project_status(tree) if tree.winfo_exists() else None)

    def _new_project(self): self._show_editor(Project(), True)
    def _edit_selected(self, tree):
        p = self._selected(tree)
        if p: self._show_editor(p, False)
    def _test_selected(self, tree):
        p = self._selected(tree)
        if not p: return
        self._background("Verifica connessione", lambda: FTPService(p, _UiLog(self)).test(), lambda result: messagebox.showinfo("Connessione riuscita", f"Cartella raggiunta:\n{result}"))
    def _run_selected(self, tree, mode):
        p = self._selected(tree)
        if not p: return
        if not messagebox.askyesno(f"Avvia ciclo {mode}", f"Avviare ora il ciclo {mode} per «{p.name}»?"): return
        self._background(f"Ciclo {mode} in esecuzione", lambda: Pipeline(p).run(mode), lambda code: messagebox.showinfo("Ciclo completato", f"Operazione terminata con codice {code}. Consulta il log del progetto per i dettagli."))
    def _delete_selected(self, tree):
        p = self._selected(tree)
        if not p or not messagebox.askyesno("Elimina progetto", f"Rimuovere la configurazione di «{p.name}»? I dati e i backup non verranno cancellati."): return
        try: scheduler_for(__import__("pathlib").Path(__file__).resolve().parents[2] / "runner.py").remove_project(p.slug)
        except Exception: pass
        self.projects = [x for x in self.projects if x.slug != p.slug]; save_projects(self.projects); self._show_projects()

    def _show_editor(self, project, is_new):
        self._clear(); self._active_nav("projects")
        self._header("Configurazione", "Nuovo progetto" if is_new else f"Modifica · {project.name}", "I campi essenziali sono indicati con *. Le password restano nella configurazione locale.")
        canvas = tk.Canvas(self.main, bg=BG, highlightthickness=0); scroll = ttk.Scrollbar(self.main, orient="vertical", command=canvas.yview); inner = ttk.Frame(canvas, style="Panel.TFrame", padding=26)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=inner, anchor="nw"); canvas.configure(yscrollcommand=scroll.set); canvas.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        self.vars = {}
        self._section(inner, "Connessione FTP", "server", [("name", "Nome progetto *", project.name), ("host", "Server *", project.host), ("port", "Porta", project.port), ("username", "Username *", project.username), ("password", "Password", project.password), ("remote_dir", "Cartella remota", project.remote_dir)])
        proto = ttk.Frame(inner, style="Panel.TFrame"); proto.pack(fill="x", pady=(0, 24)); self.vars["use_ftps"] = tk.BooleanVar(value=project.use_ftps); self.vars["verify_tls"] = tk.BooleanVar(value=project.verify_tls); self.vars["passive"] = tk.BooleanVar(value=project.passive)
        ttk.Checkbutton(proto, text="Usa FTPS", variable=self.vars["use_ftps"]).pack(side="left", padx=(0, 20)); ttk.Checkbutton(proto, text="Verifica certificato TLS", variable=self.vars["verify_tls"]).pack(side="left", padx=(0, 20)); ttk.Checkbutton(proto, text="Modalità passiva", variable=self.vars["passive"]).pack(side="left")
        compression = ttk.Frame(inner, style="Card.TFrame", padding=18); compression.pack(fill="x", pady=(0, 14))
        ttk.Label(compression, text="Compressione PDF sul server", style="Section.TLabel").pack(anchor="w")
        ttk.Label(compression, text="ATTIVA AUTOMATICAMENTE", foreground=ACCENT, background=PANEL_2, font=(self.ui_semibold, 9)).pack(anchor="w", pady=(4, 9))
        ttk.Label(compression, text="Il PDF originale viene scaricato e verificato con SHA-256. Prima si completa il trasferimento di tutti i file usando un PDF RGB compresso a 300 DPI; solo dopo il ciclo si convertono gli originali locali in TIFF bianco/nero CCITT Group 4 a 600 DPI. Lo stato e i dettagli restano registrati per ogni fase.", style="PanelMuted.TLabel", wraplength=760, justify="left").pack(anchor="w")
        self._section(inner, "Cartelle locali", "paths", [("storage_dir", "Storage cumulativo *", project.storage_dir), ("daily_backup_dir", "Backup daily *", project.daily_backup_dir), ("weekly_backup_dir", "Backup weekly *", project.weekly_backup_dir), ("secondary_backup_dir", "Copia secondaria", project.secondary_backup_dir), ("log_dir", "Log *", project.log_dir)])
        secondary = ttk.Frame(inner, style="Card.TFrame", padding=18); secondary.pack(fill="x", pady=(0, 14)); self.vars["secondary_backup_enabled"] = tk.BooleanVar(value=project.secondary_backup_enabled); ttk.Checkbutton(secondary, text="Attiva copia secondaria dopo il backup predefinito", variable=self.vars["secondary_backup_enabled"]).pack(anchor="w"); ttk.Label(secondary, text="Disattivata: il ciclo termina dopo il backup daily/weekly predefinito.", style="PanelMuted.TLabel").pack(anchor="w", pady=(5, 0))
        self._section(inner, "Retention", "retention", [("daily_keep", "Daily · copie da conservare", project.daily_keep), ("weekly_keep", "Weekly · copie da conservare", project.weekly_keep)])
        schedule = ttk.Frame(inner, style="Card.TFrame", padding=18); schedule.pack(fill="x", pady=(0, 14)); ttk.Label(schedule, text="Cicli automatici", style="Section.TLabel").pack(anchor="w"); ttk.Label(schedule, text="Le automazioni vengono eseguite da launchd mentre l’utente è connesso.", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 12)); self.vars["daily_enabled"] = tk.BooleanVar(value=project.daily_enabled); self.vars["weekly_enabled"] = tk.BooleanVar(value=project.weekly_enabled); ttk.Checkbutton(schedule, text="Attiva ciclo daily", variable=self.vars["daily_enabled"]).pack(anchor="w", pady=2); ttk.Checkbutton(schedule, text="Attiva ciclo weekly", variable=self.vars["weekly_enabled"]).pack(anchor="w", pady=2); self._time_selectors(schedule, project)
        danger = ttk.Frame(inner, style="Card.TFrame", padding=18); danger.pack(fill="x", pady=(4, 20)); ttk.Label(danger, text="Cancellazione remota", style="Section.TLabel").pack(anchor="w"); ttk.Label(danger, text="Disattivata per impostazione predefinita. Abilitala solo se sei certo del comportamento.", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 12)); self.vars["delete_remote_after_processing"] = tk.BooleanVar(value=project.delete_remote_after_processing); ttk.Checkbutton(danger, text="Elimina i file remoti dopo l'elaborazione", variable=self.vars["delete_remote_after_processing"]).pack(anchor="w"); self._field(danger, "delete_confirmation", "Scrivi CANCELLA REMOTO per confermare", project.delete_confirmation)
        actions = ttk.Frame(inner, style="Panel.TFrame"); actions.pack(fill="x", pady=(0, 6)); ttk.Button(actions, text="Annulla", command=self._show_projects).pack(side="right"); ttk.Button(actions, text="Salva progetto", style="Accent.TButton", command=lambda: self._save_editor(project, is_new)).pack(side="right", padx=(0, 10))

    def _time_selectors(self, parent, project):
        box=ttk.Frame(parent, style="Card.TFrame"); box.pack(fill="x", pady=(12, 0))
        for column, (name, label, value) in enumerate((("daily", "Orario daily", (project.daily_hour, project.daily_minute)), ("weekly", "Orario weekly", (project.weekly_hour, project.weekly_minute)))):
            holder=ttk.Frame(box, style="Card.TFrame"); holder.grid(row=0, column=column, sticky="w", padx=(0, 42) if column == 0 else (0, 0)); ttk.Label(holder, text=label, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4)); controls=ttk.Frame(holder, style="Card.TFrame"); controls.pack(anchor="w")
            hour_key=f"{name}_hour"; minute_key=f"{name}_minute"; self.vars[hour_key]=tk.StringVar(value=f"{int(value[0]):02d}"); self.vars[minute_key]=tk.StringVar(value=f"{int(value[1]):02d}")
            ttk.Combobox(controls, textvariable=self.vars[hour_key], values=[f"{i:02d}" for i in range(24)], state="readonly", width=4).pack(side="left"); ttk.Label(controls, text=":", style="PanelMuted.TLabel").pack(side="left", padx=3); ttk.Combobox(controls, textvariable=self.vars[minute_key], values=[f"{i:02d}" for i in range(60)], state="readonly", width=4).pack(side="left")

    def _section(self, parent, title, key, fields):
        box = ttk.Frame(parent, style="Panel.TFrame", padding=18); box.pack(fill="x", pady=(0, 14)); ttk.Label(box, text=title, style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14));
        for i, (name, label, value) in enumerate(fields): self._field(box, name, label, value, row=1+i//2, column=(i%2)*2)
        box.columnconfigure(1, weight=1); box.columnconfigure(3, weight=1)

    def _field(self, parent, name, label, value, row=None, column=0):
        if name not in self.vars: self.vars[name] = tk.StringVar(value=str(value if value is not None else ""))
        holder = ttk.Frame(parent, style="Panel.TFrame"); kwargs = {"fill": "x", "padx": (0, 24) if column == 0 else (0, 0), "pady": 5}
        if row is None: holder.pack(**kwargs)
        else: holder.grid(row=row, column=column, columnspan=2, sticky="ew", padx=(0, 24) if column == 0 else (0, 0), pady=5)
        ttk.Label(holder, text=label, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4)); entry = ttk.Entry(holder, textvariable=self.vars[name], show="•" if name == "password" else ""); entry.pack(fill="x")
        if name.endswith("_dir") or name == "storage_dir": ttk.Button(holder, text="Scegli…", command=lambda v=self.vars[name]: self._choose_dir(v)).pack(anchor="e", pady=(4, 0))

    def _choose_dir(self, var):
        chosen = filedialog.askdirectory();
        if chosen: var.set(chosen)

    def _save_editor(self, old, is_new):
        try:
            data = {f: self.vars[f].get() if isinstance(self.vars[f], tk.StringVar) else self.vars[f].get() for f in Project.__dataclass_fields__ if f in self.vars}
            for k in ("port", "timeout", "daily_hour", "daily_minute", "weekly_day", "weekly_hour", "weekly_minute", "daily_keep", "weekly_keep"): data[k] = int(data[k]) if k in data and str(data[k]).strip() else getattr(old, k)
            p = Project.from_dict({**old.to_dict(), **data}); p.validate()
            self.projects = [x for x in self.projects if x.slug != old.slug] if not is_new else self.projects
            self.projects.append(p) if is_new else self.projects.append(p); save_projects(self.projects); self._show_projects()
        except Exception as e: messagebox.showerror("Configurazione non valida", str(e))

    def _show_schedule(self):
        self._clear(); self._active_nav("schedule"); self._header("Automazioni", "Pianificazione", "Le automazioni vengono eseguite da launchd usando la configurazione salvata.")
        box = ttk.Frame(self.main, style="Panel.TFrame", padding=24); box.pack(fill="x")
        ttk.Label(box, text="Installazione rapida", style="Section.TLabel").pack(anchor="w"); ttk.Label(box, text="Seleziona un progetto per installare o aggiornare i task daily e weekly.", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 18))
        for p in self.projects:
            row = ttk.Frame(box, style="Card.TFrame", padding=13); row.pack(fill="x", pady=4); ttk.Label(row, text=p.name, style="Panel.TLabel").pack(side="left"); daily_state="attivo" if p.daily_enabled else "disattivo"; weekly_state="attivo" if p.weekly_enabled else "disattivo"; ttk.Label(row, text=f"{p.daily_hour:02d}:{p.daily_minute:02d} daily {daily_state}  ·  {p.weekly_hour:02d}:{p.weekly_minute:02d} weekly {weekly_state}", style="PanelMuted.TLabel").pack(side="left", padx=20); ttk.Button(row, text="Installa task", command=lambda x=p: self._install_schedule(x)).pack(side="right")
        if not self.projects: ttk.Label(box, text="Crea prima un progetto.", style="PanelMuted.TLabel").pack(anchor="w")

    def _install_schedule(self, p):
        try: scheduler_for(__import__("pathlib").Path(__file__).resolve().parents[2] / "runner.py").install_project(p); messagebox.showinfo("Pianificazione aggiornata", f"Automazioni di «{p.name}» installate.")
        except Exception as e: messagebox.showerror("Pianificazione non riuscita", str(e))

    def _show_help(self):
        self._clear(); self._active_nav("help"); self._header("Supporto", "Guida rapida", "Un flusso sicuro per conservare originali, derivati e backup verificati.")
        box = ttk.Frame(self.main, style="Panel.TFrame", padding=26); box.pack(fill="both", expand=True)
        for title, text in (("1 · Configura", "Inserisci server, credenziali e cartelle separate per storage, backup e log."), ("2 · Verifica", "Usa Verifica connessione prima del primo ciclo e prova inizialmente con cancellazione remota disattivata."), ("3 · Avvia", "Daily scarica e conserva gli originali; weekly crea un nuovo ZIP dallo storage cumulativo."), ("4 · Controlla", "Ogni ciclo scrive un report last.json e un log dettagliato nella cartella del progetto.")):
            ttk.Label(box, text=title, style="Section.TLabel").pack(anchor="w", pady=(0, 4)); ttk.Label(box, text=text, style="PanelMuted.TLabel", wraplength=700).pack(anchor="w", pady=(0, 20))

    def _background(self, title, work, done):
        progress = ttk.Progressbar(self.main, mode="indeterminate"); progress.pack(fill="x", pady=(10, 0)); progress.start(12)
        def task():
            try: result = work(); self.after(0, lambda: (progress.destroy(), done(result)))
            except Exception as e: self.after(0, lambda: (progress.destroy(), messagebox.showerror(title, str(e))))
        threading.Thread(target=task, daemon=True).start()


class _UiLog:
    def __init__(self, app): self.app = app
    def write(self, message): pass


def run():
    App().mainloop()
