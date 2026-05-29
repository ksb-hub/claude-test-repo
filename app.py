import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
from git_info import (
    get_branch_info, get_commit_graph_data,
    get_remotes, add_remote, set_remote_url, remove_remote,
    create_branch, delete_branch, fetch, pull, push,
    set_upstream, push_and_track,
    get_status, stage_file, stage_all, unstage_file, unstage_all, commit,
)

# Catppuccin Mocha palette
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
    lanes = []  # lanes[i] = expected hash or None
    for commit in commits:
        h, parents = commit["hash"], commit["parents"]

        lane = next((i for i, e in enumerate(lanes) if e == h), None)
        if lane is None:
            try:
                lane = lanes.index(None)
                lanes[lane] = h
            except ValueError:
                lane = len(lanes)
                lanes.append(h)

        commit["lane"] = lane

        if parents:
            lanes[lane] = parents[0]
            for extra in parents[1:]:
                if extra not in lanes:
                    try:
                        lanes[lanes.index(None)] = extra
                    except ValueError:
                        lanes.append(extra)
        else:
            lanes[lane] = None

    return commits


class BranchViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Git Branch Viewer")
        self.geometry("1300x740")
        self.configure(bg=BG)
        self._commits = []
        self._commit_positions = {}
        self._last_graph_hash = None
        self._auto_refresh_on = tk.BooleanVar(value=True)
        self._initial_path = sys.argv[1] if len(sys.argv) > 1 else "."
        self._apply_styles()
        self._build_ui()
        self._refresh()
        self._schedule_auto_refresh()

    # ── styles ────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("default")
        for name in ("L.Treeview", "R.Treeview"):
            s.configure(name, background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=24, font=("Consolas", 9))
            s.configure(f"{name}.Heading", background=SURFACE, foreground=BLUE,
                        font=("Consolas", 9, "bold"), relief="flat")
            s.map(name, background=[("selected", OVERLAY)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=SURFACE, foreground=TEXT,
                    padding=[12, 4], font=("Consolas", 9))
        s.map("TNotebook.Tab", background=[("selected", OVERLAY)])

    def _btn(self, parent, text, cmd, bg=OVERLAY, fg=TEXT, bold=False):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         relief="flat", padx=9, pady=2,
                         font=("Consolas", 9, "bold" if bold else "normal"),
                         activebackground=OVERLAY, cursor="hand2")

    def _section_label(self, parent, text, fg=BLUE):
        tk.Label(parent, text=text, bg=BG, fg=fg,
                 font=("Consolas", 9, "bold"), anchor="w").pack(fill="x", pady=(8, 2))

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()

        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=5)
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        left = tk.Frame(paned, bg=BG)
        paned.add(left, width=270)
        self._build_left(left)

        right = tk.Frame(paned, bg=BG)
        paned.add(right)
        self._build_right(right)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, bg=SURFACE, fg=SUBTEXT,
                 font=("Consolas", 9), anchor="w", padx=10).pack(fill="x", side="bottom")

    def _build_topbar(self):
        top = tk.Frame(self, bg=BG, pady=8)
        top.pack(fill="x", padx=10)

        tk.Label(top, text="Repository:", bg=BG, fg=TEXT,
                 font=("Consolas", 9)).pack(side="left")
        self.path_var = tk.StringVar(value=self._initial_path)
        tk.Entry(top, textvariable=self.path_var, width=44,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Consolas", 9)).pack(side="left", padx=(6, 3))

        self._btn(top, "Browse",  self._browse).pack(side="left", padx=2)
        self._btn(top, "Refresh", self._refresh).pack(side="left", padx=2)

        tk.Frame(top, bg=OVERLAY, width=1, height=20).pack(side="left", padx=10)

        self._btn(top, "Fetch", self._fetch, CYAN,  BG, bold=True).pack(side="left", padx=2)
        self._btn(top, "Pull",  self._pull,  GREEN, BG, bold=True).pack(side="left", padx=2)
        self._btn(top, "Push",  self._push,  RED,   BG, bold=True).pack(side="left", padx=2)

        tk.Frame(top, bg=OVERLAY, width=1, height=20).pack(side="left", padx=10)

        self._auto_btn = tk.Checkbutton(
            top, text="Auto-refresh (5s)", variable=self._auto_refresh_on,
            bg=BG, fg=SUBTEXT, selectcolor=BG, activebackground=BG,
            font=("Consolas", 9), cursor="hand2",
            command=self._on_auto_toggle)
        self._auto_btn.pack(side="left")

        self.last_refresh_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.last_refresh_var,
                 bg=BG, fg=OVERLAY, font=("Consolas", 8)).pack(side="left", padx=(6, 0))

    def _build_left(self, parent):
        # ── Branches ──
        self._section_label(parent, "BRANCHES", BLUE)

        bf = tk.Frame(parent, bg=BG)
        bf.pack(fill="both", expand=True)

        self.branch_tree = ttk.Treeview(bf, columns=("m", "name", "st"),
                                         show="headings", style="L.Treeview",
                                         selectmode="browse", height=10)
        self.branch_tree.heading("m",    text="")
        self.branch_tree.heading("name", text="Branch")
        self.branch_tree.heading("st",   text="Status")
        self.branch_tree.column("m",    width=22,  stretch=False, anchor="center")
        self.branch_tree.column("name", width=148, anchor="w")
        self.branch_tree.column("st",   width=72,  stretch=False, anchor="center")

        sb = ttk.Scrollbar(bf, orient="vertical", command=self.branch_tree.yview)
        self.branch_tree.configure(yscrollcommand=sb.set)
        self.branch_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for tag, fg in [("current", GREEN), ("ahead", BLUE), ("behind", RED),
                        ("synced", SUBTEXT), ("no_remote", YELLOW),
                        ("remote_only", PURPLE), ("section", OVERLAY)]:
            self.branch_tree.tag_configure(tag, foreground=fg)
        self.branch_tree.tag_configure("current", foreground=GREEN, background="#1e3a2f")

        br = tk.Frame(parent, bg=BG)
        br.pack(fill="x", pady=(4, 0))
        self._btn(br, "+ New",    self._create_branch,  GREEN,  BG, bold=True).pack(side="left", padx=(0, 4))
        self._btn(br, "- Delete", self._delete_branch,  RED,    BG, bold=True).pack(side="left", padx=(0, 4))
        self._btn(br, "⇄ Link",   self._link_upstream,  ORANGE, BG, bold=True).pack(side="left")

        tk.Frame(parent, bg=OVERLAY, height=1).pack(fill="x", pady=8)

        # ── Remotes ──
        self._section_label(parent, "REMOTES", PURPLE)

        rf = tk.Frame(parent, bg=BG)
        rf.pack(fill="both", expand=True)

        self.remote_tree = ttk.Treeview(rf, columns=("name", "url"),
                                         show="headings", style="R.Treeview",
                                         selectmode="browse", height=5)
        self.remote_tree.heading("name", text="Name")
        self.remote_tree.heading("url",  text="URL")
        self.remote_tree.column("name", width=55,  stretch=False, anchor="w")
        self.remote_tree.column("url",  width=170, anchor="w")

        sb2 = ttk.Scrollbar(rf, orient="vertical", command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=sb2.set)
        self.remote_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        rr = tk.Frame(parent, bg=BG)
        rr.pack(fill="x", pady=(4, 0))
        self._btn(rr, "+ Add",  self._add_remote,    PURPLE, BG, bold=True).pack(side="left", padx=(0, 4))
        self._btn(rr, "Edit",   self._edit_remote,   OVERLAY, TEXT).pack(side="left", padx=(0, 4))
        self._btn(rr, "Remove", self._remove_remote, RED,     BG).pack(side="left")

    def _build_right(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)

        # ── Tab 1: Branch Graph ──
        graph_tab = tk.Frame(nb, bg=BG)
        nb.add(graph_tab, text="  Branch Graph  ")
        self._build_graph_tab(graph_tab)

        # ── Tab 2: Changes ──
        changes_tab = tk.Frame(nb, bg=BG)
        nb.add(changes_tab, text="  Changes  ")
        self._build_changes_tab(changes_tab)

    def _build_graph_tab(self, parent):
        cf = tk.Frame(parent, bg=BG2)
        cf.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(cf, bg=BG2, highlightthickness=0)
        vsc = ttk.Scrollbar(cf, orient="vertical",   command=self.canvas.yview)
        hsc = ttk.Scrollbar(cf, orient="horizontal",  command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsc.set, xscrollcommand=hsc.set)
        vsc.pack(side="right",  fill="y")
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
        paned = tk.PanedWindow(parent, orient="vertical", bg=BG, sashwidth=5)
        paned.pack(fill="both", expand=True)

        # ── Unstaged ──
        top = tk.Frame(paned, bg=BG)
        paned.add(top, height=200)

        hdr = tk.Frame(top, bg=BG)
        hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(hdr, text="UNSTAGED CHANGES", bg=BG, fg=YELLOW,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self._btn(hdr, "Stage All ▲", self._stage_all, YELLOW, BG, bold=True).pack(side="right")

        uf = tk.Frame(top, bg=BG)
        uf.pack(fill="both", expand=True, padx=10)

        self.unstaged_tree = ttk.Treeview(uf, columns=("status", "file"),
                                           show="headings", style="L.Treeview",
                                           selectmode="extended")
        self.unstaged_tree.heading("status", text="")
        self.unstaged_tree.heading("file",   text="File")
        self.unstaged_tree.column("status", width=70,  stretch=False, anchor="center")
        self.unstaged_tree.column("file",   width=500, anchor="w")
        sb = ttk.Scrollbar(uf, orient="vertical", command=self.unstaged_tree.yview)
        self.unstaged_tree.configure(yscrollcommand=sb.set)
        self.unstaged_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.unstaged_tree.tag_configure("modified",  foreground=YELLOW)
        self.unstaged_tree.tag_configure("untracked", foreground=SUBTEXT)
        self.unstaged_tree.tag_configure("deleted",   foreground=RED)
        self.unstaged_tree.bind("<Double-1>", self._stage_selected)

        tk.Label(top, text="  double-click or →", bg=BG, fg=OVERLAY,
                 font=("Consolas", 8, "italic")).pack(anchor="w", padx=10)
        self._btn(top, "Stage Selected ▲", self._stage_selected, YELLOW, BG).pack(anchor="e", padx=10, pady=4)

        # ── Staged ──
        mid = tk.Frame(paned, bg=BG)
        paned.add(mid, height=150)

        hdr2 = tk.Frame(mid, bg=BG)
        hdr2.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(hdr2, text="STAGED CHANGES", bg=BG, fg=GREEN,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self._btn(hdr2, "Unstage All ▼", self._unstage_all, OVERLAY, TEXT).pack(side="right")

        sf = tk.Frame(mid, bg=BG)
        sf.pack(fill="both", expand=True, padx=10)

        self.staged_tree = ttk.Treeview(sf, columns=("status", "file"),
                                         show="headings", style="L.Treeview",
                                         selectmode="extended")
        self.staged_tree.heading("status", text="")
        self.staged_tree.heading("file",   text="File")
        self.staged_tree.column("status", width=70,  stretch=False, anchor="center")
        self.staged_tree.column("file",   width=500, anchor="w")
        sb2 = ttk.Scrollbar(sf, orient="vertical", command=self.staged_tree.yview)
        self.staged_tree.configure(yscrollcommand=sb2.set)
        self.staged_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.staged_tree.tag_configure("staged", foreground=GREEN)
        self.staged_tree.bind("<Double-1>", self._unstage_selected)

        tk.Label(mid, text="  double-click or ↓", bg=BG, fg=OVERLAY,
                 font=("Consolas", 8, "italic")).pack(anchor="w", padx=10)
        self._btn(mid, "Unstage Selected ▼", self._unstage_selected, OVERLAY, TEXT).pack(anchor="e", padx=10, pady=4)

        # ── Commit ──
        bot = tk.Frame(paned, bg=BG)
        paned.add(bot, height=130)

        tk.Label(bot, text="COMMIT MESSAGE", bg=BG, fg=BLUE,
                 font=("Consolas", 9, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 2))

        self.commit_msg = tk.Text(bot, height=3, bg=SURFACE, fg=TEXT,
                                   insertbackground=TEXT, relief="flat",
                                   font=("Consolas", 10), padx=8, pady=6,
                                   wrap="word")
        self.commit_msg.pack(fill="x", padx=10)

        btn_row = tk.Frame(bot, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=6)
        self._btn(btn_row, "Commit", self._do_commit, BLUE, BG, bold=True).pack(side="right", padx=(4, 0))
        self._btn(btn_row, "Commit & Push", self._do_commit_push, GREEN, BG, bold=True).pack(side="right")

    # ── data ──────────────────────────────────────────────────

    def _refresh(self):
        for row in self.branch_tree.get_children():
            self.branch_tree.delete(row)
        try:
            self.info = get_branch_info(self.path_var.get())
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))
            return

        local, tracked = self.info["local"], set()
        self.branch_tree.insert("", "end", values=("", "── LOCAL ──", ""), tags=("section",))
        for b in local:
            if b["remote"]:
                tracked.add(b["remote"])
            if b["ahead"] and b["behind"]:
                st, tag = f"↑{b['ahead']}↓{b['behind']}", "behind"
            elif b["ahead"]:
                st, tag = f"↑{b['ahead']}", "ahead"
            elif b["behind"]:
                st, tag = f"↓{b['behind']}", "behind"
            elif b["remote"]:
                st, tag = "synced", "synced"
            else:
                st, tag = "no remote", "no_remote"
            if b["current"]:
                tag = "current"
            self.branch_tree.insert("", "end",
                                     values=("●" if b["current"] else " ", b["name"], st),
                                     tags=(tag,))

        untracked = [r for r in self.info["remote"] if r not in tracked]
        if untracked:
            self.branch_tree.insert("", "end", values=("", "── REMOTE ──", ""), tags=("section",))
            for r in untracked:
                self.branch_tree.insert("", "end", values=(" ", r, "remote"), tags=("remote_only",))

        self._load_remotes()
        self._load_status()
        self._draw_graph()
        self.status_var.set(
            f"{len(local)} local  |  {len(self.info['remote'])} remote  |  {self.path_var.get()}"
        )

    def _load_remotes(self):
        for row in self.remote_tree.get_children():
            self.remote_tree.delete(row)
        try:
            for name, url in get_remotes(self.path_var.get()).items():
                self.remote_tree.insert("", "end", values=(name, url))
        except RuntimeError:
            pass

    def _draw_graph(self):
        self.canvas.delete("all")
        try:
            commits = get_commit_graph_data(self.path_var.get(), n=80)
        except RuntimeError:
            return
        if not commits:
            self.canvas.create_text(20, 30, text="No commits found.",
                                    fill=SUBTEXT, font=("Consolas", 10), anchor="w")
            return

        commits = assign_lanes(commits)
        self._commits = commits
        self._commit_positions = {}

        max_lane  = max(c["lane"] for c in commits)
        text_x    = GRAPH_L + (max_lane + 1) * LANE_W + 18
        total_h   = len(commits) * ROW_H + 30
        total_w   = max(text_x + 700, 900)
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

        hash_to_commit = {c["hash"]: c for c in commits}

        # Pre-compute positions
        for i, c in enumerate(commits):
            cy = i * ROW_H + ROW_H // 2 + 12
            cx = GRAPH_L + c["lane"] * LANE_W + LANE_W // 2
            self._commit_positions[c["hash"]] = (cx, cy)

        # Draw lines
        for c in commits:
            cx, cy = self._commit_positions[c["hash"]]
            color   = LANE_COLORS[c["lane"] % len(LANE_COLORS)]

            for j, ph in enumerate(c["parents"]):
                if ph not in self._commit_positions:
                    continue
                px, py  = self._commit_positions[ph]
                p_lane  = hash_to_commit[ph]["lane"]
                p_color = LANE_COLORS[p_lane % len(LANE_COLORS)]

                if cx == px:
                    self.canvas.create_line(
                        cx, cy + COMMIT_R, px, py - COMMIT_R,
                        fill=color, width=2)
                else:
                    mid = cy + ROW_H // 2
                    self.canvas.create_line(cx, cy + COMMIT_R, cx, mid,
                                            fill=color, width=2)
                    self.canvas.create_line(cx, mid, px, mid,
                                            fill=p_color, width=2)
                    self.canvas.create_line(px, mid, px, py - COMMIT_R,
                                            fill=p_color, width=2)

        # Draw circles + labels
        for c in commits:
            cx, cy = self._commit_positions[c["hash"]]
            color  = LANE_COLORS[c["lane"] % len(LANE_COLORS)]
            is_head = any("HEAD ->" in r for r in c["refs"])

            # HEAD 커밋은 바깥에 흰 링 추가
            if is_head:
                self.canvas.create_oval(
                    cx - COMMIT_R - 4, cy - COMMIT_R - 4,
                    cx + COMMIT_R + 4, cy + COMMIT_R + 4,
                    fill="", outline=color, width=2,
                    tags=(f"node_{c['hash']}",))

            self.canvas.create_oval(
                cx - COMMIT_R, cy - COMMIT_R,
                cx + COMMIT_R, cy + COMMIT_R,
                fill=color, outline=BG2, width=2,
                tags=(f"node_{c['hash']}",))

            # Ref badges
            label_x = text_x
            for ref in c["refs"][:3]:
                if "HEAD ->" in ref:
                    display = ref.replace("HEAD -> ", "")
                    bg_col, fg_col = GREEN, BG2
                elif "origin/" in ref or "/" in ref:
                    display = ref
                    bg_col, fg_col = CYAN, BG2
                else:
                    display = ref
                    bg_col, fg_col = YELLOW, BG2

                tid = self.canvas.create_text(
                    label_x + 4, cy, text=f" {display} ",
                    fill=fg_col, font=("Consolas", 8, "bold"), anchor="w")
                bbox = self.canvas.bbox(tid)
                if bbox:
                    self.canvas.create_rectangle(
                        bbox[0] - 2, bbox[1], bbox[2] + 2, bbox[3],
                        fill=bg_col, outline="", tags="badge")
                    self.canvas.tag_raise(tid)
                    label_x = bbox[2] + 8

            # Commit message
            msg = c["message"][:60]
            self.canvas.create_text(
                label_x, cy,
                text=f"{c['short']}  {msg}",
                fill=SUBTEXT, font=("Consolas", 9), anchor="w",
                tags=(f"node_{c['hash']}",))

    def _on_canvas_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for c in self._commits:
            cx, cy = self._commit_positions.get(c["hash"], (None, None))
            if cx is None:
                continue
            if abs(x - cx) <= COMMIT_R + 5 and abs(y - cy) <= COMMIT_R + 5:
                refs = "  ".join(c["refs"]) if c["refs"] else "—"
                self.detail_var.set(
                    f"  {c['short']}  |  {c['author']}  |  {c['date']}"
                    f"  |  {refs}  |  {c['message']}")
                return

    # ── changes tab ───────────────────────────────────────────

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
            self.unstaged_tree.insert("", "end",
                                       values=(f"[{f['label']}]", f["file"]),
                                       tags=(tag,))
        for f in status["staged"]:
            self.staged_tree.insert("", "end",
                                     values=(f"[{f['label']}]", f["file"]),
                                     tags=("staged",))

    def _stage_selected(self, _=None):
        sel = self.unstaged_tree.selection()
        if not sel:
            messagebox.showinfo("Stage", "Select files to stage.")
            return
        for item in sel:
            filepath = self.unstaged_tree.item(item, "values")[1]
            try:
                stage_file(self.path_var.get(), filepath)
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))
                return
        self._load_status()

    def _stage_all(self):
        try:
            stage_all(self.path_var.get())
            self._load_status()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _unstage_selected(self, _=None):
        sel = self.staged_tree.selection()
        if not sel:
            messagebox.showinfo("Unstage", "Select files to unstage.")
            return
        for item in sel:
            filepath = self.staged_tree.item(item, "values")[1]
            try:
                unstage_file(self.path_var.get(), filepath)
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))
                return
        self._load_status()

    def _unstage_all(self):
        try:
            unstage_all(self.path_var.get())
            self._load_status()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _do_commit(self):
        msg = self.commit_msg.get("1.0", "end").strip()
        if not msg:
            messagebox.showwarning("Commit", "Please enter a commit message.")
            return
        try:
            commit(self.path_var.get(), msg)
            self.commit_msg.delete("1.0", "end")
            self.status_var.set("Committed successfully.")
            self._load_status()
            self._draw_graph()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    def _do_commit_push(self):
        msg = self.commit_msg.get("1.0", "end").strip()
        if not msg:
            messagebox.showwarning("Commit", "Please enter a commit message.")
            return
        try:
            commit(self.path_var.get(), msg)
            self.commit_msg.delete("1.0", "end")
            self.status_var.set("Committed. Pushing...")
            self.update()
            push(self.path_var.get())
            self.status_var.set("Committed & pushed successfully.")
            self._load_status()
            self._draw_graph()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e))

    # ── auto refresh ──────────────────────────────────────────

    def _schedule_auto_refresh(self):
        if self._auto_refresh_on.get():
            self._check_and_refresh()
        self.after(5000, self._schedule_auto_refresh)

    def _check_and_refresh(self):
        # VS Code 연동: 임시 파일에서 새 경로 감지
        import os
        sync_file = os.path.join(os.environ.get("TEMP", ""), "gitviewer_path.txt")
        if os.path.exists(sync_file):
            try:
                with open(sync_file, "r", encoding="utf-8") as f:
                    new_path = f.read().strip()
                if new_path and new_path != self.path_var.get():
                    self.path_var.set(new_path)
                    self._last_graph_hash = None
                    self.status_var.set(f"VS Code workspace changed → {new_path}")
            except Exception:
                pass

        # 변경 감지 후 그래프 갱신
        try:
            from git_info import _run
            current = _run(["log", "--oneline", "--all", "-1"], cwd=self.path_var.get())
        except Exception:
            return
        if current != self._last_graph_hash:
            self._last_graph_hash = current
            self._refresh()
            self.last_refresh_var.set(f"updated {datetime.now().strftime('%H:%M:%S')}")

    def _on_auto_toggle(self):
        state = "ON" if self._auto_refresh_on.get() else "OFF"
        self.status_var.set(f"Auto-refresh {state}")

    # ── git ops ───────────────────────────────────────────────

    def _run_git(self, fn, label):
        self.status_var.set(f"{label}...")
        self.update()
        try:
            fn(self.path_var.get())
            self.status_var.set(f"{label} done.")
            self._refresh()
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
            self._refresh()

    def _create_branch(self):
        name = simpledialog.askstring("New Branch", "Branch name:", parent=self)
        if name:
            try:
                create_branch(self.path_var.get(), name.strip())
                self._refresh()
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _delete_branch(self):
        sel = self.branch_tree.selection()
        if not sel:
            messagebox.showinfo("Delete Branch", "Select a branch first.")
            return
        name = self.branch_tree.item(sel[0], "values")[1]
        if "──" in name:
            return
        if messagebox.askyesno("Delete Branch", f"Delete branch '{name}'?"):
            try:
                delete_branch(self.path_var.get(), name)
                self._refresh()
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _add_remote(self):
        name = simpledialog.askstring("Add Remote", "Remote name (e.g. origin):", parent=self)
        if not name:
            return
        url = simpledialog.askstring("Add Remote", f"URL for '{name}':", parent=self)
        if url:
            try:
                add_remote(self.path_var.get(), name.strip(), url.strip())
                self._load_remotes()
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _edit_remote(self):
        sel = self.remote_tree.selection()
        if not sel:
            messagebox.showinfo("Edit Remote", "Select a remote first.")
            return
        name, old_url = self.remote_tree.item(sel[0], "values")
        url = simpledialog.askstring("Edit Remote", f"New URL for '{name}':",
                                      initialvalue=old_url, parent=self)
        if url:
            try:
                set_remote_url(self.path_var.get(), name, url.strip())
                self._load_remotes()
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))

    def _link_upstream(self):
        sel = self.branch_tree.selection()
        if not sel:
            messagebox.showinfo("Link Remote", "Select a local branch first.")
            return

        item = self.branch_tree.item(sel[0])
        tags = item["tags"]
        local_name = item["values"][1]

        # 섹션 헤더나 remote-only 항목은 허용하지 않음
        if "──" in local_name or "section" in tags or "remote_only" in tags:
            messagebox.showinfo("Link Remote", "Please select a local branch (not a section or remote-only branch).")
            return

        remotes = get_remotes(self.path_var.get())
        remote_branches = self.info.get("remote", [])

        if not remotes:
            messagebox.showinfo("Link Remote", "No remotes configured.\nAdd a remote first.")
            return

        # 이미 추적 중인 원격 브랜치 정보 전달
        local_info = next((b for b in self.info["local"] if b["name"] == local_name), None)
        current_remote = local_info["remote"] if local_info else None

        LinkDialog(self, local_name, list(remotes.keys()), remote_branches,
                   self.path_var.get(), self._refresh, current_remote)

    def _remove_remote(self):
        sel = self.remote_tree.selection()
        if not sel:
            messagebox.showinfo("Remove Remote", "Select a remote first.")
            return
        name = self.remote_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Remove Remote", f"Remove remote '{name}'?"):
            try:
                remove_remote(self.path_var.get(), name)
                self._load_remotes()
            except RuntimeError as e:
                messagebox.showerror("Git Error", str(e))


class LinkDialog(tk.Toplevel):
    """브랜치를 원격 브랜치에 연결하거나 새로 push하는 다이얼로그"""

    def __init__(self, parent, local_branch, remote_names, remote_branches,
                 repo_path, on_done, current_remote=None):
        super().__init__(parent)
        self.title(f"Link '{local_branch}' to Remote")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        self._local          = local_branch
        self._remote_names   = remote_names
        self._remote_branches = remote_branches
        self._repo           = repo_path
        self._on_done        = on_done

        pad = {"padx": 16, "pady": 4}

        # 현재 상태 표시
        tk.Label(self, text=f"  Local branch:  {local_branch}",
                 bg=BG, fg=GREEN, font=("Consolas", 10, "bold")).pack(anchor="w", padx=16, pady=(12, 2))

        status_text = f"  Currently tracking:  {current_remote}" if current_remote else "  Currently tracking:  (none)"
        status_fg   = CYAN if current_remote else YELLOW
        tk.Label(self, text=status_text, bg=BG, fg=status_fg,
                 font=("Consolas", 9)).pack(anchor="w", padx=16, pady=(0, 8))

        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16)

        # ── Option 1: 기존 원격 브랜치에 연결 ──
        has_remote = bool(remote_branches)
        o1_fg = TEXT if has_remote else OVERLAY
        tk.Label(self, text="Option A — Connect to existing remote branch:",
                 bg=BG, fg=o1_fg, font=("Consolas", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 2))

        if has_remote:
            self._existing_var = tk.StringVar(value=remote_branches[0])
            om = tk.OptionMenu(self, self._existing_var, *remote_branches)
            om.configure(bg=SURFACE, fg=TEXT, relief="flat",
                         font=("Consolas", 9), highlightthickness=0,
                         activebackground=OVERLAY)
            om["menu"].configure(bg=SURFACE, fg=TEXT, font=("Consolas", 9))
            om.pack(anchor="w", padx=16)
            tk.Button(self, text="Set Upstream →",
                      command=self._set_upstream,
                      bg=BLUE, fg=BG, relief="flat", padx=10,
                      font=("Consolas", 9, "bold"), cursor="hand2").pack(anchor="w", padx=16, pady=(6, 4))
        else:
            tk.Label(self, text="  (원격 브랜치 없음 — Fetch 후 재시도)",
                     bg=BG, fg=OVERLAY, font=("Consolas", 9, "italic")).pack(anchor="w", padx=16)

        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16, pady=(8, 0))

        # ── Option 2: 원격에 새로 push + track ──
        tk.Label(self, text="Option B — Push this branch to remote & track:",
                 bg=BG, fg=TEXT, font=("Consolas", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 2))

        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", padx=16)
        self._remote_var = tk.StringVar(value=remote_names[0])
        om2 = tk.OptionMenu(row, self._remote_var, *remote_names)
        om2.configure(bg=SURFACE, fg=TEXT, relief="flat",
                      font=("Consolas", 9), highlightthickness=0,
                      activebackground=OVERLAY)
        om2["menu"].configure(bg=SURFACE, fg=TEXT, font=("Consolas", 9))
        om2.pack(side="left")
        tk.Label(row, text=f" / {local_branch}", bg=BG, fg=SUBTEXT,
                 font=("Consolas", 9)).pack(side="left")

        tk.Label(self, text="  → 원격에 브랜치가 없을 때 사용",
                 bg=BG, fg=SUBTEXT, font=("Consolas", 8, "italic")).pack(anchor="w", padx=16)

        tk.Button(self, text="Push & Track ↑",
                  command=self._push_and_track,
                  bg=GREEN, fg=BG, relief="flat", padx=10,
                  font=("Consolas", 9, "bold"), cursor="hand2").pack(anchor="w", padx=16, pady=(6, 4))

        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", padx=16, pady=(8, 0))

        tk.Button(self, text="Cancel", command=self.destroy,
                  bg=OVERLAY, fg=TEXT, relief="flat", padx=10,
                  font=("Consolas", 9)).pack(pady=10)

        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw-w)//2}+{py + (ph-h)//2}")

    def _set_upstream(self):
        target = self._existing_var.get()
        if "(no" in target:
            messagebox.showwarning("No Remote Branch", "No remote branches available.", parent=self)
            return
        try:
            set_upstream(self._repo, self._local, target)
            messagebox.showinfo("Done", f"'{self._local}' now tracks '{target}'", parent=self)
            self.destroy()
            self._on_done()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e), parent=self)

    def _push_and_track(self):
        remote = self._remote_var.get()
        try:
            push_and_track(self._repo, self._local, remote)
            messagebox.showinfo("Done",
                                f"Pushed '{self._local}' to '{remote}' and set as upstream.",
                                parent=self)
            self.destroy()
            self._on_done()
        except RuntimeError as e:
            messagebox.showerror("Git Error", str(e), parent=self)


if __name__ == "__main__":
    app = BranchViewer()
    app.mainloop()
