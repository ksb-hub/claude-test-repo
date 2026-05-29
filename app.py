import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
from git_info import (
    get_branch_info, get_commit_graph_data,
    get_remotes, add_remote, set_remote_url, remove_remote,
    create_branch, delete_branch, fetch, pull, push,
    set_upstream, push_and_track,
    get_status, stage_file, stage_all, unstage_file, unstage_all, commit,
    checkout_branch, merge_branch, discard_file, discard_all_changes,
)

# Catppuccin Mocha
BG      = "#1e1e2e"
BG2     = "#181825"
SURFACE = "#313244"
OVERLAY = "#45475a"
TEXT    = "#cdd6f4"
SUBTEXT = "#a6adc8"
GREEN   = "#a6e3a1"
BLUE    = "#89b4fa"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
PURPLE  = "#cba6f7"
CYAN    = "#89dceb"
ORANGE  = "#fab387"

LANE_COLORS = [BLUE, GREEN, PURPLE, ORANGE, CYAN, YELLOW, RED,
               "#eba0ac", "#94e2d5", "#f2cdcd"]

ROW_H    = 46
LANE_W   = 22
COMMIT_R = 8
GRAPH_L  = 16


def assign_lanes(commits):
    lanes = []
    for c in commits:
        h, parents = c["hash"], c["parents"]
        lane = next((i for i, e in enumerate(lanes) if e == h), None)
        if lane is None:
            try:
                lane = lanes.index(None); lanes[lane] = h
            except ValueError:
                lane = len(lanes); lanes.append(h)
        c["lane"] = lane
        if parents:
            lanes[lane] = parents[0]
            for extra in parents[1:]:
                if extra not in lanes:
                    try: lanes[lanes.index(None)] = extra
                    except ValueError: lanes.append(extra)
        else:
            lanes[lane] = None
    return commits


class BranchViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Git Branch Viewer")
        self.geometry("1340x760")
        self.configure(bg=BG)
        self._commits           = []
        self._commit_positions  = {}
        self._last_graph_hash   = None
        self._last_status_hash  = None
        self._is_auto_msg       = False
        self._auto_refresh_on   = tk.BooleanVar(value=True)
        self._initial_path      = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
        self.info               = {"local": [], "remote": []}
        self._apply_styles()
        self._build_ui()
        self._refresh()
        self.after(5000, self._auto_refresh_tick)

    # ── styles ──────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("default")
        for n in ("L.Treeview", "R.Treeview"):
            s.configure(n, background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=26, font=("Consolas", 9))
            s.configure(f"{n}.Heading", background=SURFACE, foreground=BLUE,
                        font=("Consolas", 9, "bold"), relief="flat")
            s.map(n, background=[("selected", OVERLAY)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=SURFACE, foreground=SUBTEXT,
                    padding=[14, 6], font=("Consolas", 9))
        s.map("TNotebook.Tab",
              background=[("selected", OVERLAY)],
              foreground=[("selected", TEXT)])

    def _btn(self, parent, text, cmd, bg=OVERLAY, fg=TEXT, bold=False):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         relief="flat", padx=9, pady=3,
                         font=("Consolas", 9, "bold" if bold else "normal"),
                         activebackground=OVERLAY, activeforeground=TEXT,
                         cursor="hand2")

    def _gbtn(self, parent, text, cmd, bg, bold=False):
        """Grid용 전폭 버튼"""
        fg = BG if bg not in (OVERLAY, SURFACE) else TEXT
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         relief="flat", pady=4,
                         font=("Consolas", 8, "bold" if bold else "normal"),
                         activebackground=OVERLAY, cursor="hand2")

    # ── toast ───────────────────────────────────────────────────

    def _toast(self, msg, color=GREEN):
        t = tk.Label(self, text=f"  {msg}  ", bg=color, fg=BG,
                     font=("Consolas", 9, "bold"), pady=7, padx=14)
        t.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-44)
        self.after(2500, t.destroy)

    # ── UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=5)
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        left = tk.Frame(paned, bg=BG)
        paned.add(left, width=290)
        self._build_left(left)
        right = tk.Frame(paned, bg=BG)
        paned.add(right)
        self._build_right(right)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, bg=SURFACE, fg=SUBTEXT,
                 font=("Consolas", 9), anchor="w", padx=12).pack(fill="x", side="bottom")

    def _build_topbar(self):
        top = tk.Frame(self, bg=BG, pady=8)
        top.pack(fill="x", padx=10)
        tk.Label(top, text="Repo:", bg=BG, fg=SUBTEXT, font=("Consolas", 9)).pack(side="left")
        self.path_var = tk.StringVar(value=self._initial_path)
        tk.Entry(top, textvariable=self.path_var, width=38,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Consolas", 9)).pack(side="left", padx=(4, 3))
        self._btn(top, "Browse",    self._browse).pack(side="left", padx=2)
        self._btn(top, "⟳ Refresh", self._refresh, BLUE, BG, bold=True).pack(side="left", padx=2)
        tk.Frame(top, bg=OVERLAY, width=1, height=20).pack(side="left", padx=8)
        self._btn(top, "↓ Fetch", self._fetch, CYAN,  BG, bold=True).pack(side="left", padx=2)
        self._btn(top, "↓ Pull",  self._pull,  GREEN, BG, bold=True).pack(side="left", padx=2)
        self._btn(top, "↑ Push",  self._push,  RED,   BG, bold=True).pack(side="left", padx=2)
        tk.Frame(top, bg=OVERLAY, width=1, height=20).pack(side="left", padx=8)
        self.cur_branch_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.cur_branch_var,
                 bg=BG, fg=GREEN, font=("Consolas", 9, "bold")).pack(side="left")
        tk.Checkbutton(top, text="Auto", variable=self._auto_refresh_on,
                       bg=BG, fg=SUBTEXT, selectcolor=BG, activebackground=BG,
                       font=("Consolas", 8), cursor="hand2").pack(side="right")
        self.last_refresh_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.last_refresh_var,
                 bg=BG, fg=OVERLAY, font=("Consolas", 8)).pack(side="right", padx=(0, 4))

    def _build_left(self, parent):
        # BRANCHES
        tk.Label(parent, text="BRANCHES", bg=BG, fg=BLUE,
                 font=("Consolas", 9, "bold"), anchor="w").pack(fill="x", pady=(6, 2))
        bf = tk.Frame(parent, bg=BG)
        bf.pack(fill="both", expand=True)
        self.branch_tree = ttk.Treeview(bf, columns=("m", "name", "st"),
                                         show="headings", style="L.Treeview",
                                         selectmode="browse", height=10)
        self.branch_tree.heading("m",    text="")
        self.branch_tree.heading("name", text="Branch")
        self.branch_tree.heading("st",   text="Status")
        self.branch_tree.column("m",    width=22,  stretch=False, anchor="center")
        self.branch_tree.column("name", width=155, anchor="w")
        self.branch_tree.column("st",   width=72,  stretch=False, anchor="center")
        sb = ttk.Scrollbar(bf, orient="vertical", command=self.branch_tree.yview)
        self.branch_tree.configure(yscrollcommand=sb.set)
        self.branch_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, fg, bg_c in [
            ("current",     GREEN,  "#1e3a2f"),
            ("ahead",       BLUE,   BG2),
            ("behind",      RED,    BG2),
            ("synced",      SUBTEXT,BG2),
            ("no_remote",   YELLOW, BG2),
            ("remote_only", PURPLE, BG2),
            ("section",     OVERLAY,BG2),
        ]:
            self.branch_tree.tag_configure(tag, foreground=fg, background=bg_c)
        self.branch_tree.bind("<Double-1>",         self._on_branch_double)
        self.branch_tree.bind("<Button-3>",         self._show_branch_menu)

        # 브랜치 버튼 — 2열 그리드
        br = tk.Frame(parent, bg=BG)
        br.pack(fill="x", pady=(6, 0))
        br.columnconfigure(0, weight=1)
        br.columnconfigure(1, weight=1)
        self._gbtn(br, "+ New",      self._create_branch,    GREEN,  bold=True).grid(row=0, column=0, sticky="ew", padx=(0,2), pady=2)
        self._gbtn(br, "✕ Delete",   self._delete_branch,    RED,    bold=True).grid(row=0, column=1, sticky="ew", padx=(2,0), pady=2)
        self._gbtn(br, "↪ Checkout", self._checkout_selected, CYAN,  bold=True).grid(row=1, column=0, sticky="ew", padx=(0,2), pady=2)
        self._gbtn(br, "⊕ Merge",   self._merge_selected,   ORANGE, bold=True).grid(row=1, column=1, sticky="ew", padx=(2,0), pady=2)
        self._gbtn(br, "⇄ Link Remote", self._link_upstream, SURFACE).grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)

        tk.Frame(parent, bg=OVERLAY, height=1).pack(fill="x", pady=8)

        # REMOTES
        tk.Label(parent, text="REMOTES", bg=BG, fg=PURPLE,
                 font=("Consolas", 9, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        rf = tk.Frame(parent, bg=BG)
        rf.pack(fill="both", expand=True)
        self.remote_tree = ttk.Treeview(rf, columns=("name", "url"),
                                         show="headings", style="R.Treeview",
                                         selectmode="browse", height=4)
        self.remote_tree.heading("name", text="Name")
        self.remote_tree.heading("url",  text="URL")
        self.remote_tree.column("name", width=55,  stretch=False, anchor="w")
        self.remote_tree.column("url",  width=175, anchor="w")
        sb2 = ttk.Scrollbar(rf, orient="vertical", command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=sb2.set)
        self.remote_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        # 리모트 버튼 — 2열 그리드
        rr = tk.Frame(parent, bg=BG)
        rr.pack(fill="x", pady=(6, 0))
        rr.columnconfigure(0, weight=1)
        rr.columnconfigure(1, weight=1)
        self._gbtn(rr, "+ Add Remote",  self._add_remote,    PURPLE, bold=True).grid(row=0, column=0, sticky="ew", padx=(0,2), pady=2)
        self._gbtn(rr, "Edit URL",      self._edit_remote,   SURFACE).grid(row=0, column=1, sticky="ew", padx=(2,0), pady=2)
        self._gbtn(rr, "⇄ Link Branch", self._link_upstream, ORANGE, bold=True).grid(row=1, column=0, sticky="ew", padx=(0,2), pady=2)
        self._gbtn(rr, "Remove",        self._remove_remote, RED).grid(row=1, column=1, sticky="ew", padx=(2,0), pady=2)

    def _build_right(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        g = tk.Frame(nb, bg=BG); nb.add(g, text="  Branch Graph  "); self._build_graph_tab(g)
        c = tk.Frame(nb, bg=BG); nb.add(c, text="  Changes  ");       self._build_changes_tab(c)
        m = tk.Frame(nb, bg=BG); nb.add(m, text="  Merge  ");         self._build_merge_tab(m)

    def _build_graph_tab(self, parent):
        cf = tk.Frame(parent, bg=BG2)
        cf.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(cf, bg=BG2, highlightthickness=0)
        vsc = ttk.Scrollbar(cf, orient="vertical",   command=self.canvas.yview)
        hsc = ttk.Scrollbar(cf, orient="horizontal",  command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsc.set, xscrollcommand=hsc.set)
        vsc.pack(side="right", fill="y")
        hsc.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<MouseWheel>",
                         lambda e: self.canvas.yview_scroll(-(e.delta // 120), "units"))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        detail = tk.Frame(parent, bg=SURFACE, pady=5)
        detail.pack(fill="x")
        self.detail_var = tk.StringVar(value="  Click a commit node to see details")
        tk.Label(detail, textvariable=self.detail_var, bg=SURFACE, fg=TEXT,
                 font=("Consolas", 9), anchor="w", padx=10).pack(fill="x")

    def _build_changes_tab(self, parent):
        paned = tk.PanedWindow(parent, orient="vertical", bg=BG, sashwidth=4)
        paned.pack(fill="both", expand=True)

        # ── UNSTAGED ──
        top = tk.Frame(paned, bg=BG); paned.add(top, height=210)
        hdr = tk.Frame(top, bg=BG)
        hdr.pack(fill="x", padx=10, pady=(8, 3))
        tk.Label(hdr, text="UNSTAGED", bg=BG, fg=YELLOW,
                 font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(hdr, text="  double-click → stage", bg=BG, fg=OVERLAY,
                 font=("Consolas", 8, "italic")).pack(side="left", padx=4)
        self._btn(hdr, "Stage All ▲",   self._stage_all,   YELLOW, BG, bold=True).pack(side="right")
        self._btn(hdr, "⚠ Discard All", self._discard_all, RED,    BG, bold=True).pack(side="right", padx=(0,4))
        uf = tk.Frame(top, bg=BG)
        uf.pack(fill="both", expand=True, padx=10, pady=(0, 2))
        self.unstaged_tree = ttk.Treeview(uf, columns=("st","file"), show="headings",
                                           style="L.Treeview", selectmode="extended")
        self.unstaged_tree.heading("st",   text="Status")
        self.unstaged_tree.heading("file", text="File")
        self.unstaged_tree.column("st",   width=80,  stretch=False, anchor="center")
        self.unstaged_tree.column("file", width=500, anchor="w")
        sb = ttk.Scrollbar(uf, orient="vertical", command=self.unstaged_tree.yview)
        self.unstaged_tree.configure(yscrollcommand=sb.set)
        self.unstaged_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.unstaged_tree.tag_configure("modified",  foreground=YELLOW)
        self.unstaged_tree.tag_configure("untracked", foreground=SUBTEXT)
        self.unstaged_tree.tag_configure("deleted",   foreground=RED)
        self.unstaged_tree.bind("<Double-1>", self._stage_selected)
        self.unstaged_tree.bind("<Button-3>", self._show_unstaged_menu)
        br = tk.Frame(top, bg=BG)
        br.pack(fill="x", padx=10, pady=(2, 4))
        self._btn(br, "Stage ▲",    self._stage_selected,   YELLOW, BG, bold=True).pack(side="left", padx=(0,4))
        self._btn(br, "⚠ Discard", self._discard_selected, RED,    BG, bold=True).pack(side="left")

        # ── STAGED ──
        mid = tk.Frame(paned, bg=BG); paned.add(mid, height=160)
        hdr2 = tk.Frame(mid, bg=BG)
        hdr2.pack(fill="x", padx=10, pady=(8, 3))
        tk.Label(hdr2, text="STAGED", bg=BG, fg=GREEN,
                 font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(hdr2, text="  double-click → unstage", bg=BG, fg=OVERLAY,
                 font=("Consolas", 8, "italic")).pack(side="left", padx=4)
        self._btn(hdr2, "✕ Clear All",   self._force_clear_staged, RED,    BG, bold=True).pack(side="right")
        self._btn(hdr2, "Unstage All ▼", self._unstage_all,        OVERLAY,TEXT).pack(side="right", padx=(0,4))
        sf = tk.Frame(mid, bg=BG)
        sf.pack(fill="both", expand=True, padx=10, pady=(0, 2))
        self.staged_tree = ttk.Treeview(sf, columns=("st","file"), show="headings",
                                         style="L.Treeview", selectmode="extended")
        self.staged_tree.heading("st",   text="Status")
        self.staged_tree.heading("file", text="File")
        self.staged_tree.column("st",   width=80,  stretch=False, anchor="center")
        self.staged_tree.column("file", width=500, anchor="w")
        sb2 = ttk.Scrollbar(mid, orient="vertical", command=self.staged_tree.yview)
        self.staged_tree.configure(yscrollcommand=sb2.set)
        self.staged_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.staged_tree.tag_configure("staged", foreground=GREEN)
        self.staged_tree.bind("<Double-1>", self._unstage_selected)
        br2 = tk.Frame(mid, bg=BG)
        br2.pack(fill="x", padx=10, pady=(2, 4))
        self._btn(br2, "Unstage ▼", self._unstage_selected, OVERLAY, TEXT).pack(side="left")

        # ── COMMIT ──
        bot = tk.Frame(paned, bg=BG); paned.add(bot, height=140)
        msg_hdr = tk.Frame(bot, bg=BG)
        msg_hdr.pack(fill="x", padx=10, pady=(8, 3))
        tk.Label(msg_hdr, text="COMMIT MESSAGE", bg=BG, fg=BLUE,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self.auto_label = tk.Label(msg_hdr, text="", bg=BG, fg=PURPLE,
                                    font=("Consolas", 8, "italic"))
        self.auto_label.pack(side="left", padx=6)
        self.commit_msg = tk.Text(bot, height=3, bg=SURFACE, fg=TEXT,
                                   insertbackground=TEXT, relief="flat",
                                   font=("Consolas", 10), padx=8, pady=6, wrap="word")
        self.commit_msg.pack(fill="x", padx=10)
        self.commit_msg.bind("<Control-Return>", lambda e: self._do_commit())
        self.commit_msg.bind("<Key>", self._on_msg_edit)
        btn_row = tk.Frame(bot, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=6)
        tk.Label(btn_row, text="Ctrl+Enter to commit", bg=BG, fg=OVERLAY,
                 font=("Consolas", 8, "italic")).pack(side="left")
        self._btn(btn_row, "Commit & Push ↑", self._do_commit_push, GREEN, BG, bold=True).pack(side="right", padx=(4,0))
        self._btn(btn_row, "Commit",           self._do_commit,      BLUE,  BG, bold=True).pack(side="right")

    def _build_merge_tab(self, parent):
        w = tk.Frame(parent, bg=BG)
        w.pack(fill="both", expand=True, padx=30, pady=20)
        tk.Label(w, text="MERGE BRANCHES", bg=BG, fg=ORANGE,
                 font=("Consolas", 11, "bold"), anchor="w").pack(fill="x", pady=(0,16))
        r1 = tk.Frame(w, bg=BG); r1.pack(fill="x", pady=4)
        tk.Label(r1, text="Merge INTO  (target):", bg=BG, fg=SUBTEXT,
                 font=("Consolas", 9), width=22, anchor="w").pack(side="left")
        self.merge_target_var = tk.StringVar(value="(current branch)")
        tk.Label(r1, textvariable=self.merge_target_var, bg=SURFACE, fg=GREEN,
                 font=("Consolas", 10, "bold"), padx=10, pady=4).pack(side="left")
        r2 = tk.Frame(w, bg=BG); r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Merge FROM  (source):", bg=BG, fg=SUBTEXT,
                 font=("Consolas", 9), width=22, anchor="w").pack(side="left")
        self.merge_src_var = tk.StringVar()
        self.merge_src_menu = ttk.Combobox(r2, textvariable=self.merge_src_var,
                                            state="readonly", width=30, font=("Consolas", 10))
        self.merge_src_menu.pack(side="left")
        tk.Frame(w, bg=OVERLAY, height=1).pack(fill="x", pady=16)
        tk.Label(w, text="Merge strategy:", bg=BG, fg=SUBTEXT,
                 font=("Consolas", 9), anchor="w").pack(fill="x")
        self.merge_strategy = tk.StringVar(value="no-ff")
        for val, label, col in [
            ("no-ff",    "Create merge commit always  (--no-ff)", BLUE),
            ("default",  "Fast-forward if possible    (default)",  SUBTEXT),
            ("squash",   "Squash all commits into one (--squash)", PURPLE),
        ]:
            f = tk.Frame(w, bg=BG); f.pack(fill="x", pady=2)
            tk.Radiobutton(f, text=label, variable=self.merge_strategy, value=val,
                           bg=BG, fg=col, selectcolor=BG, activebackground=BG,
                           font=("Consolas", 9), cursor="hand2").pack(side="left")
        tk.Frame(w, bg=OVERLAY, height=1).pack(fill="x", pady=16)
        self._btn(w, "⊕  Execute Merge", self._do_merge, ORANGE, BG, bold=True).pack(anchor="w", pady=(0,4))
        tk.Label(w, text="⚠  Ensure your working tree is clean before merging.",
                 bg=BG, fg=OVERLAY, font=("Consolas", 8, "italic")).pack(anchor="w")

    # ── data ────────────────────────────────────────────────────

    def _refresh(self):
        for row in self.branch_tree.get_children():
            self.branch_tree.delete(row)
        try:
            self.info = get_branch_info(self.path_var.get())
        except RuntimeError as e:
            self.status_var.set(f"Error: {e}"); return

        local, tracked = self.info["local"], set()
        current_name = next((b["name"] for b in local if b["current"]), "")
        self.cur_branch_var.set(f"  ⎇  {current_name}" if current_name else "")
        self.merge_target_var.set(current_name or "(current branch)")
        other = [b["name"] for b in local if not b["current"]]
        self.merge_src_menu["values"] = other
        self.merge_src_var.set(other[0] if other else "")

        self.branch_tree.insert("", "end", values=("","── LOCAL ──",""), tags=("section",))
        for b in local:
            if b["remote"]: tracked.add(b["remote"])
            if b["ahead"] and b["behind"]:  st, tag = f"↑{b['ahead']}↓{b['behind']}", "behind"
            elif b["ahead"]:                 st, tag = f"↑{b['ahead']}",               "ahead"
            elif b["behind"]:                st, tag = f"↓{b['behind']}",              "behind"
            elif b["remote"]:                st, tag = "synced",                        "synced"
            else:                            st, tag = "no remote",                     "no_remote"
            if b["current"]: tag = "current"
            self.branch_tree.insert("", "end",
                                     values=("●" if b["current"] else " ", b["name"], st),
                                     tags=(tag,))
        untracked = [r for r in self.info["remote"] if r not in tracked]
        if untracked:
            self.branch_tree.insert("", "end", values=("","── REMOTE ──",""), tags=("section",))
            for r in untracked:
                self.branch_tree.insert("", "end", values=(" ", r, "remote"), tags=("remote_only",))

        self._load_remotes()
        self._load_status()
        self._draw_graph()
        self.status_var.set(f"{len(local)} local  |  {len(self.info['remote'])} remote  |  {self.path_var.get()}")

    def _load_remotes(self):
        for row in self.remote_tree.get_children():
            self.remote_tree.delete(row)
        try:
            for name, url in get_remotes(self.path_var.get()).items():
                self.remote_tree.insert("", "end", values=(name, url))
        except RuntimeError:
            pass

    def _load_status(self):
        for row in self.unstaged_tree.get_children():
            self.unstaged_tree.delete(row)
        for row in self.staged_tree.get_children():
            self.staged_tree.delete(row)
        try:
            status = get_status(self.path_var.get())
        except RuntimeError:
            return
        for f in status["unstaged"]:
            tag = {"M": "modified", "?": "untracked", "D": "deleted"}.get(f["code"], "modified")
            self.unstaged_tree.insert("", "end", values=(f"[{f['label']}]", f["file"]), tags=(tag,))
        for f in status["staged"]:
            self.staged_tree.insert("", "end", values=(f"[{f['label']}]", f["file"]), tags=("staged",))

    def _draw_graph(self):
        self.canvas.delete("all")
        try:
            commits = get_commit_graph_data(self.path_var.get(), n=80)
        except RuntimeError:
            return
        if not commits:
            self.canvas.create_text(20, 30, text="No commits.", fill=SUBTEXT,
                                    font=("Consolas", 10), anchor="w"); return
        commits = assign_lanes(commits)
        self._commits = commits
        self._commit_positions = {}
        max_lane = max(c["lane"] for c in commits)
        text_x   = GRAPH_L + (max_lane + 1) * LANE_W + 18
        self.canvas.configure(scrollregion=(0, 0, max(text_x + 700, 900),
                                            len(commits) * ROW_H + 30))
        h2c = {c["hash"]: c for c in commits}
        for i, c in enumerate(commits):
            self._commit_positions[c["hash"]] = (
                GRAPH_L + c["lane"] * LANE_W + LANE_W // 2,
                i * ROW_H + ROW_H // 2 + 12)
        for c in commits:
            cx, cy = self._commit_positions[c["hash"]]
            col = LANE_COLORS[c["lane"] % len(LANE_COLORS)]
            for ph in c["parents"]:
                if ph not in self._commit_positions: continue
                px, py  = self._commit_positions[ph]
                pc = LANE_COLORS[h2c[ph]["lane"] % len(LANE_COLORS)]
                if cx == px:
                    self.canvas.create_line(cx, cy+COMMIT_R, px, py-COMMIT_R, fill=col, width=2)
                else:
                    mid = cy + ROW_H // 2
                    self.canvas.create_line(cx, cy+COMMIT_R, cx, mid, fill=col, width=2)
                    self.canvas.create_line(cx, mid, px, mid, fill=pc, width=2)
                    self.canvas.create_line(px, mid, px, py-COMMIT_R, fill=pc, width=2)
        for c in commits:
            cx, cy  = self._commit_positions[c["hash"]]
            col     = LANE_COLORS[c["lane"] % len(LANE_COLORS)]
            is_head = any("HEAD ->" in r for r in c["refs"])
            if is_head:
                self.canvas.create_oval(cx-COMMIT_R-4, cy-COMMIT_R-4,
                                        cx+COMMIT_R+4, cy+COMMIT_R+4,
                                        fill="", outline=col, width=2)
            self.canvas.create_oval(cx-COMMIT_R, cy-COMMIT_R,
                                    cx+COMMIT_R, cy+COMMIT_R,
                                    fill=col, outline=BG2, width=2,
                                    tags=(f"node_{c['hash']}",))
            lx = text_x
            for ref in c["refs"][:3]:
                if "HEAD ->" in ref: display, bg_c = ref.replace("HEAD -> ",""), GREEN
                elif "/" in ref:     display, bg_c = ref, CYAN
                else:                display, bg_c = ref, YELLOW
                tid = self.canvas.create_text(lx+4, cy, text=f" {display} ",
                                              fill=BG2, font=("Consolas",8,"bold"), anchor="w")
                bbox = self.canvas.bbox(tid)
                if bbox:
                    self.canvas.create_rectangle(bbox[0]-2, bbox[1], bbox[2]+2, bbox[3],
                                                 fill=bg_c, outline="", tags="badge")
                    self.canvas.tag_raise(tid)
                    lx = bbox[2] + 8
            self.canvas.create_text(lx, cy, text=f"{c['short']}  {c['message'][:55]}",
                                    fill=SUBTEXT, font=("Consolas",9), anchor="w",
                                    tags=(f"node_{c['hash']}",))

    def _on_canvas_click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for c in self._commits:
            cx, cy = self._commit_positions.get(c["hash"], (None, None))
            if cx and abs(x-cx) <= COMMIT_R+5 and abs(y-cy) <= COMMIT_R+5:
                self.detail_var.set(
                    f"  {c['short']}  |  {c['author']}  |  {c['date']}"
                    f"  |  {'  '.join(c['refs']) or '—'}  |  {c['message']}")
                return

    # ── branch interactions ──────────────────────────────────────

    def _get_sel_branch(self):
        sel = self.branch_tree.selection()
        if not sel: return None, None
        item = self.branch_tree.item(sel[0])
        name, tags = item["values"][1], item["tags"]
        if "──" in str(name) or "section" in tags: return None, None
        return name, tags

    def _on_branch_double(self, _=None):
        name, tags = self._get_sel_branch()
        if not name or "current" in tags or "remote_only" in tags: return
        self._checkout_named(name)

    def _show_branch_menu(self, event):
        item = self.branch_tree.identify_row(event.y)
        if not item: return
        self.branch_tree.selection_set(item)
        name, tags = self._get_sel_branch()
        if not name: return
        is_cur = "current" in tags
        is_rem = "remote_only" in tags
        menu = tk.Menu(self, tearoff=0, bg=SURFACE, fg=TEXT,
                       activebackground=OVERLAY, font=("Consolas", 9))
        if not is_cur and not is_rem:
            menu.add_command(label=f"↪  Checkout '{name}'",
                             command=lambda: self._checkout_named(name))
            menu.add_command(label=f"⊕  Merge '{name}' into current",
                             command=lambda: self._merge_named(name))
            menu.add_separator()
        if not is_rem:
            menu.add_command(label=f"↑  Push '{name}'",
                             command=lambda: self._push_branch_named(name))
            menu.add_command(label="⇄  Set Upstream...", command=self._link_upstream)
        if not is_cur:
            menu.add_separator()
            menu.add_command(label=f"✕  Delete '{name}'",
                             command=lambda: self._delete_named(name))
        menu.tk_popup(event.x_root, event.y_root)

    def _checkout_selected(self):
        name, tags = self._get_sel_branch()
        if not name: messagebox.showinfo("Checkout", "Select a branch first."); return
        if "current" in tags: self._toast("Already on this branch.", YELLOW); return
        self._checkout_named(name)

    def _checkout_named(self, name):
        try:
            checkout_branch(self.path_var.get(), name)
            self._refresh(); self._toast(f"Switched to '{name}'")
        except RuntimeError as e:
            messagebox.showerror("Checkout Error", str(e))

    def _merge_selected(self):
        name, tags = self._get_sel_branch()
        if not name: messagebox.showinfo("Merge", "Select a branch to merge."); return
        if "current" in tags: self._toast("Cannot merge into itself.", YELLOW); return
        self._merge_named(name)

    def _merge_named(self, name):
        current = next((b["name"] for b in self.info["local"] if b["current"]), "current")
        strategy = self.merge_strategy.get()
        if not messagebox.askyesno("Merge", f"Merge '{name}' into '{current}'?\nStrategy: {strategy}"): return
        try:
            merge_branch(self.path_var.get(), name, strategy)
            self._refresh(); self._toast(f"Merged '{name}' into '{current}'")
        except RuntimeError as e:
            messagebox.showerror("Merge Error", str(e))

    def _do_merge(self):
        src = self.merge_src_var.get()
        if not src: messagebox.showinfo("Merge", "Select a source branch."); return
        self._merge_named(src)

    def _push_branch_named(self, name):
        remotes = get_remotes(self.path_var.get())
        remote  = list(remotes.keys())[0] if remotes else "origin"
        try:
            from git_info import _run
            _run(["push", remote, name], cwd=self.path_var.get())
            self._refresh(); self._toast(f"Pushed '{name}' → {remote}")
        except RuntimeError as e:
            messagebox.showerror("Push Error", str(e))

    def _delete_named(self, name):
        if messagebox.askyesno("Delete", f"Delete branch '{name}'?"):
            try:
                delete_branch(self.path_var.get(), name)
                self._refresh(); self._toast(f"Deleted '{name}'", RED)
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    # ── auto commit message ──────────────────────────────────────

    def _generate_commit_msg(self):
        try: status = get_status(self.path_var.get())
        except RuntimeError: return
        staged = status["staged"]
        if not staged: return
        def names(files, n=2):
            ns = [f["file"].split("/")[-1].split("\\")[-1] for f in files[:n]]
            return ", ".join(ns) + (f" (+{len(files)-n} more)" if len(files) > n else "")
        parts = []
        added    = [f for f in staged if f["code"] == "A"]
        modified = [f for f in staged if f["code"] == "M"]
        deleted  = [f for f in staged if f["code"] == "D"]
        renamed  = [f for f in staged if f["code"] == "R"]
        if added:    parts.append(f"Add {names(added)}")
        if modified: parts.append(f"Update {names(modified)}")
        if deleted:  parts.append(f"Remove {names(deleted)}")
        if renamed:  parts.append(f"Rename {len(renamed)} file(s)")
        msg = "; ".join(parts)
        if not msg: return
        if not self._is_auto_msg and self.commit_msg.get("1.0", "end").strip(): return
        self.commit_msg.delete("1.0", "end")
        self.commit_msg.insert("1.0", msg)
        self.commit_msg.configure(fg=PURPLE)
        self.auto_label.configure(text="✦ auto-generated")
        self._is_auto_msg = True

    def _on_msg_edit(self, event=None):
        if event and event.keysym in ("Control_L","Control_R","Shift_L","Shift_R",
                                       "Alt_L","Alt_R","Return","Caps_Lock"): return
        if self._is_auto_msg:
            self._is_auto_msg = False
            self.commit_msg.configure(fg=TEXT)
            self.auto_label.configure(text="")

    def _reset_commit_state(self):
        self.commit_msg.delete("1.0", "end")
        self.commit_msg.configure(fg=TEXT)
        self.auto_label.configure(text="")
        self._is_auto_msg = False

    # ── changes tab ─────────────────────────────────────────────

    def _show_unstaged_menu(self, event):
        item = self.unstaged_tree.identify_row(event.y)
        if not item: return
        self.unstaged_tree.selection_set(item)
        vals        = self.unstaged_tree.item(item, "values")
        filepath    = vals[1]
        is_untracked = vals[0] == "[untracked]"
        menu = tk.Menu(self, tearoff=0, bg=SURFACE, fg=TEXT,
                       activebackground=OVERLAY, font=("Consolas", 9))
        menu.add_command(label=f"Stage ▲  '{filepath}'", command=self._stage_selected)
        menu.add_separator()
        label = "Delete file" if is_untracked else f"Discard changes  '{filepath}'"
        menu.add_command(label=f"⚠  {label}",
                         command=lambda: self._discard_one(filepath, is_untracked))
        menu.tk_popup(event.x_root, event.y_root)

    def _discard_one(self, filepath, is_untracked=False):
        verb = "Delete" if is_untracked else "Discard changes to"
        if not messagebox.askyesno("⚠ Confirm", f"{verb} '{filepath}'?\nThis cannot be undone."): return
        try:
            discard_file(self.path_var.get(), filepath, untracked=is_untracked)
            self._load_status(); self._toast(f"Discarded '{filepath}'", RED)
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _discard_selected(self, _=None):
        sel = self.unstaged_tree.selection()
        if not sel: messagebox.showinfo("Discard", "Select files to discard."); return
        files = [self.unstaged_tree.item(i, "values") for i in sel]
        names = ", ".join(v[1] for v in files)
        if not messagebox.askyesno("⚠ Confirm Discard",
                                    f"Discard changes to:\n{names}\n\nThis cannot be undone!"): return
        for vals in files:
            is_untracked = vals[0] == "[untracked]"
            try: discard_file(self.path_var.get(), vals[1], untracked=is_untracked)
            except RuntimeError as e: messagebox.showerror("Git Error", str(e)); break
        self._load_status(); self._toast(f"Discarded {len(files)} file(s)", RED)

    def _discard_all(self):
        if not self.unstaged_tree.get_children(): return
        if not messagebox.askyesno("⚠ Discard ALL", "Discard ALL unstaged changes?\nThis cannot be undone!"): return
        try: discard_all_changes(self.path_var.get())
        except RuntimeError as e: messagebox.showerror("Git Error", str(e)); return
        for item in self.unstaged_tree.get_children():
            vals = self.unstaged_tree.item(item, "values")
            if vals[0] == "[untracked]":
                try: discard_file(self.path_var.get(), vals[1], untracked=True)
                except Exception: pass
        self._load_status(); self._toast("All unstaged changes discarded", RED)

    def _stage_selected(self, _=None):
        sel = self.unstaged_tree.selection()
        if not sel: messagebox.showinfo("Stage", "Select files to stage."); return
        for item in sel:
            try: stage_file(self.path_var.get(), self.unstaged_tree.item(item, "values")[1])
            except RuntimeError as e: messagebox.showerror("Git Error", str(e)); return
        self._load_status(); self._generate_commit_msg(); self._toast("Staged")

    def _stage_all(self):
        try:
            stage_all(self.path_var.get())
            self._load_status(); self._generate_commit_msg(); self._toast("All files staged")
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _unstage_selected(self, _=None):
        sel = self.staged_tree.selection()
        if not sel: messagebox.showinfo("Unstage", "Select files to unstage."); return
        for item in sel:
            try: unstage_file(self.path_var.get(), self.staged_tree.item(item, "values")[1])
            except RuntimeError as e: messagebox.showerror("Git Error", str(e)); return
        self._load_status(); self._toast("Unstaged", YELLOW)

    def _unstage_all(self):
        try:
            unstage_all(self.path_var.get())
            self._load_status(); self._toast("All files unstaged", YELLOW)
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _force_clear_staged(self):
        items = self.staged_tree.get_children()
        if not items:
            self._load_status(); self._toast("Staged list is already empty", YELLOW); return
        from git_info import _run
        cleared, phantom = [], []
        for item in items:
            fp = self.staged_tree.item(item, "values")[1]
            try: _run(["restore", "--staged", fp], cwd=self.path_var.get()); cleared.append(fp)
            except RuntimeError:
                try: _run(["rm", "--cached", fp], cwd=self.path_var.get()); cleared.append(fp)
                except RuntimeError:
                    self.staged_tree.delete(item); phantom.append(fp)
        self._load_status()
        msg = f"Cleared {len(cleared)}"
        if phantom: msg += f" + removed {len(phantom)} phantom"
        self._toast(msg, GREEN if not phantom else YELLOW)

    def _do_commit(self):
        msg = self.commit_msg.get("1.0", "end").strip()
        if not msg: self._toast("Enter a commit message.", YELLOW); return
        try:
            commit(self.path_var.get(), msg)
            self._reset_commit_state()
            self._load_status(); self._draw_graph()
            self._toast("Committed!")
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _do_commit_push(self):
        msg = self.commit_msg.get("1.0", "end").strip()
        if not msg: self._toast("Enter a commit message.", YELLOW); return
        try:
            commit(self.path_var.get(), msg)
            self._reset_commit_state()
            self.status_var.set("Pushing..."); self.update()
            push(self.path_var.get())
            self._load_status(); self._draw_graph()
            self._toast("Committed & Pushed!")
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    # ── auto refresh ────────────────────────────────────────────

    def _auto_refresh_tick(self):
        if self._auto_refresh_on.get():
            self._check_and_refresh()
        self.after(5000, self._auto_refresh_tick)

    def _check_and_refresh(self):
        sync_file = os.path.join(os.environ.get("TEMP", ""), "gitviewer_path.txt")
        if os.path.exists(sync_file):
            try:
                with open(sync_file, "r", encoding="utf-8") as f:
                    new_path = f.read().strip()
                if new_path and new_path != self.path_var.get():
                    self.path_var.set(new_path)
                    self._last_graph_hash  = None
                    self._last_status_hash = None
                    self.status_var.set(f"VS Code → {new_path}")
            except Exception:
                pass
        try:
            from git_info import _run
            commit_hash = _run(["log","--oneline","--all","-1"], cwd=self.path_var.get())
            status_hash = _run(["status","--porcelain"],          cwd=self.path_var.get())
        except Exception:
            return
        if commit_hash != self._last_graph_hash:
            self._last_graph_hash  = commit_hash
            self._last_status_hash = status_hash
            self._refresh()
            self.last_refresh_var.set(datetime.now().strftime("%H:%M:%S"))
        elif status_hash != self._last_status_hash:
            self._last_status_hash = status_hash
            self._load_status()
            self.last_refresh_var.set(datetime.now().strftime("%H:%M:%S"))

    # ── git ops ─────────────────────────────────────────────────

    def _run_git(self, fn, label):
        self.status_var.set(f"{label}..."); self.update()
        try:
            fn(self.path_var.get()); self._refresh(); self._toast(f"{label} done")
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))
            self.status_var.set(f"{label} failed.")

    def _fetch(self): self._run_git(fetch, "Fetch")
    def _pull(self):  self._run_git(pull,  "Pull")
    def _push(self):  self._run_git(push,  "Push")

    def _browse(self):
        path = filedialog.askdirectory(title="Select Git Repository")
        if path:
            self.path_var.set(path)
            self._last_graph_hash = self._last_status_hash = None
            self._refresh()

    def _create_branch(self):
        name = simpledialog.askstring("New Branch", "Branch name:", parent=self)
        if name:
            try:
                create_branch(self.path_var.get(), name.strip())
                self._refresh(); self._toast(f"Created '{name}'")
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _delete_branch(self):
        name, _ = self._get_sel_branch()
        if not name: messagebox.showinfo("Delete", "Select a branch first."); return
        self._delete_named(name)

    # ── remote ops ──────────────────────────────────────────────

    def _add_remote(self):
        name = simpledialog.askstring("Add Remote", "Remote name:", parent=self)
        if not name: return
        url = simpledialog.askstring("Add Remote", f"URL for '{name}':", parent=self)
        if url:
            try:
                add_remote(self.path_var.get(), name.strip(), url.strip())
                self._load_remotes(); self._toast(f"Added remote '{name}'")
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _edit_remote(self):
        sel = self.remote_tree.selection()
        if not sel: messagebox.showinfo("Edit Remote", "Select a remote first."); return
        name, old_url = self.remote_tree.item(sel[0], "values")
        url = simpledialog.askstring("Edit Remote", f"New URL for '{name}':",
                                      initialvalue=old_url, parent=self)
        if url:
            try:
                set_remote_url(self.path_var.get(), name, url.strip())
                self._load_remotes(); self._toast("Remote URL updated")
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _remove_remote(self):
        sel = self.remote_tree.selection()
        if not sel: messagebox.showinfo("Remove Remote", "Select a remote first."); return
        name = self.remote_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Remove Remote", f"Remove remote '{name}'?"):
            try:
                remove_remote(self.path_var.get(), name)
                self._load_remotes(); self._toast(f"Removed '{name}'", RED)
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _link_upstream(self):
        sel = self.branch_tree.selection()
        if not sel: messagebox.showinfo("Link Remote", "Select a local branch first."); return
        item = self.branch_tree.item(sel[0])
        tags, local_name = item["tags"], item["values"][1]
        if "──" in str(local_name) or "section" in tags or "remote_only" in tags:
            messagebox.showinfo("Link Remote", "Please select a local branch."); return
        remotes = get_remotes(self.path_var.get())
        if not remotes: messagebox.showinfo("Link Remote", "No remotes configured."); return
        local_info     = next((b for b in self.info["local"] if b["name"] == local_name), None)
        current_remote = local_info["remote"] if local_info else None
        LinkDialog(self, local_name, list(remotes.keys()), self.info.get("remote", []),
                   self.path_var.get(), self._refresh, current_remote)


# ── Link Dialog ─────────────────────────────────────────────────

class LinkDialog(tk.Toplevel):
    def __init__(self, parent, local_branch, remote_names, remote_branches,
                 repo_path, on_done, current_remote=None):
        super().__init__(parent)
        self.title(f"Link '{local_branch}' to Remote")
        self.configure(bg=BG); self.resizable(False, False); self.grab_set()
        self._local, self._repo, self._on_done = local_branch, repo_path, on_done

        tk.Label(self, text=f"  Local: {local_branch}", bg=BG, fg=GREEN,
                 font=("Consolas", 10, "bold")).pack(anchor="w", padx=16, pady=(12,2))
        status = f"  Tracking: {current_remote}" if current_remote else "  Tracking: (none)"
        tk.Label(self, text=status, bg=BG, fg=CYAN if current_remote else YELLOW,
                 font=("Consolas", 9)).pack(anchor="w", padx=16, pady=(0,8))
        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16)

        tk.Label(self, text="Option A — Connect to existing remote branch:",
                 bg=BG, fg=TEXT if remote_branches else OVERLAY,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=16, pady=(10,2))
        if remote_branches:
            self._existing_var = tk.StringVar(value=remote_branches[0])
            om = tk.OptionMenu(self, self._existing_var, *remote_branches)
            om.configure(bg=SURFACE, fg=TEXT, relief="flat", font=("Consolas",9),
                         highlightthickness=0, activebackground=OVERLAY)
            om["menu"].configure(bg=SURFACE, fg=TEXT, font=("Consolas",9))
            om.pack(anchor="w", padx=16)
            tk.Button(self, text="Set Upstream →", command=self._set_upstream,
                      bg=BLUE, fg=BG, relief="flat", padx=10,
                      font=("Consolas",9,"bold"), cursor="hand2").pack(anchor="w", padx=16, pady=(6,4))
        else:
            tk.Label(self, text="  (no remote branches — run Fetch first)",
                     bg=BG, fg=OVERLAY, font=("Consolas",9,"italic")).pack(anchor="w", padx=16)

        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16, pady=(8,0))
        tk.Label(self, text="Option B — Push & track (new remote branch):",
                 bg=BG, fg=TEXT, font=("Consolas",9,"bold")).pack(anchor="w", padx=16, pady=(10,2))
        row = tk.Frame(self, bg=BG); row.pack(anchor="w", padx=16)
        self._remote_var = tk.StringVar(value=remote_names[0] if remote_names else "origin")
        om2 = tk.OptionMenu(row, self._remote_var, *(remote_names or ["origin"]))
        om2.configure(bg=SURFACE, fg=TEXT, relief="flat", font=("Consolas",9),
                      highlightthickness=0, activebackground=OVERLAY)
        om2["menu"].configure(bg=SURFACE, fg=TEXT, font=("Consolas",9))
        om2.pack(side="left")
        tk.Label(row, text=f" / {local_branch}", bg=BG, fg=SUBTEXT,
                 font=("Consolas",9)).pack(side="left")
        tk.Label(self, text="  → 원격에 브랜치가 없을 때 사용",
                 bg=BG, fg=SUBTEXT, font=("Consolas",8,"italic")).pack(anchor="w", padx=16)
        tk.Button(self, text="Push & Track ↑", command=self._push_and_track,
                  bg=GREEN, fg=BG, relief="flat", padx=10,
                  font=("Consolas",9,"bold"), cursor="hand2").pack(anchor="w", padx=16, pady=(6,4))
        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16, pady=(8,0))
        tk.Button(self, text="Cancel", command=self.destroy,
                  bg=OVERLAY, fg=TEXT, relief="flat", padx=10,
                  font=("Consolas",9)).pack(pady=10)
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px+(pw-w)//2}+{py+(ph-h)//2}")

    def _set_upstream(self):
        try:
            set_upstream(self._repo, self._local, self._existing_var.get())
            self.destroy(); self._on_done()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e), parent=self)

    def _push_and_track(self):
        try:
            push_and_track(self._repo, self._local, self._remote_var.get())
            self.destroy(); self._on_done()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e), parent=self)


if __name__ == "__main__":
    app = BranchViewer()
    app.mainloop()
