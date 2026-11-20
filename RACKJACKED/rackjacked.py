"""RACKJACKED - one rack, every tool.

A single-window catalog over the whole tool list: search, filter by flag,
browse by category, and see at a glance which tools are already alive on
this machine.

CREATED BY  XxREPTILExX  x  XxNEOPAULxX
"""

import os
import queue
import shutil
import sys
import threading
import webbrowser

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from catalog import CATEGORIES, FLAG_MEANINGS, TOOLS

# ----------------------------------------------------------------------------
# palette - blue / turquoise / silver / black
# ----------------------------------------------------------------------------
BG = "#0B0F14"
PANEL = "#111823"
PANEL_ALT = "#0E141D"
EDGE = "#1E2A38"
TEXT = "#C9D4E0"
MUTED = "#7C8B9B"
TURQ = "#2EC4B6"
TURQ_DIM = "#1B8B82"
BLUE = "#2F81F7"
SILVER = "#C9D1D9"
WARN = "#E0A458"
GREEN = "#4FC98A"
RED = "#E05A5A"

APP_NAME = "RACKJACKED"
APP_VER = "1.0.0"


def _dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _res(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def flags_os(flags):
    oses = []
    if "L" in flags:
        oses.append("LNX")
    if "W" in flags:
        oses.append("WIN")
    return "+".join(oses) if oses else "-"


def probe(bins):
    """Return the first binary or module that actually resolves on this box."""
    for name in bins:
        if not name:
            continue
        if shutil.which(name):
            return name
        try:
            import importlib.util
            if importlib.util.find_spec(name) is not None:
                return name + " (py)"
        except Exception:
            pass
    return ""


class RackJacked(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " v" + APP_VER)
        self.geometry("1160x740")
        self.minsize(940, 600)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        try:
            self.iconbitmap(default=_res("icon.ico"))
        except Exception:
            pass

        self.found = {}            # tool name -> resolved binary/module
        self._q = queue.Queue()    # worker -> main handoff
        self._scanning = False
        self.active_flags = set()
        self.active_cat = "ALL"
        self.installed_only = False
        self.query = ""
        self.sort_col = "TOOL"
        self.sort_desc = False
        self.rows = {}             # treeview iid -> tool dict

        self._fonts()
        self._style()
        self._build_header()
        self._build_toolbar()
        self._build_body()
        self._build_status()

        self.bind("<Control-f>", lambda e: (self.search.focus_set(), self.search.select_range(0, "end")))
        self.bind("<Escape>", self._clear_all)
        self.search.focus_set()

        self.refresh()
        self.after(120, self._rescan)

    # -- fonts ---------------------------------------------------------------
    def _fonts(self):
        fam = "Segoe UI"
        mono = "Consolas"
        self.f_word = tkfont.Font(family=fam, size=20, weight="bold")
        self.f_sub = tkfont.Font(family=fam, size=9)
        self.f_sig = tkfont.Font(family=fam, size=8, weight="bold")
        self.f_small = tkfont.Font(family=fam, size=9)
        self.f_meta = tkfont.Font(family=mono, size=8)
        self.f_body = tkfont.Font(family=fam, size=10)
        self.f_big = tkfont.Font(family=fam, size=15, weight="bold")
        self.f_list = tkfont.Font(family=mono, size=9)

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Rack.Treeview",
                    background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=23, borderwidth=0, font=self.f_small)
        s.configure("Rack.Treeview.Heading",
                    background=PANEL_ALT, foreground=MUTED, relief="flat",
                    font=self.f_small, borderwidth=0)
        s.map("Rack.Treeview.Heading", background=[("active", EDGE)])
        s.map("Rack.Treeview",
              background=[("selected", "#1B3A52")],
              foreground=[("selected", "#E8F6F4")])
        s.configure("Rack.Vertical.TScrollbar",
                    background=PANEL_ALT, troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, borderwidth=0)

    # -- header --------------------------------------------------------------
    def _build_header(self):
        h = tk.Frame(self, bg=BG)
        h.pack(fill="x", padx=16, pady=(12, 0))

        left = tk.Frame(h, bg=BG)
        left.pack(side="left")
        tk.Label(left, text=APP_NAME, bg=BG, fg=TURQ, font=self.f_word).pack(anchor="w")
        tk.Label(left, text="one rack - every tool - %d entries" % len(TOOLS),
                 bg=BG, fg=MUTED, font=self.f_sub).pack(anchor="w")

        right = tk.Frame(h, bg=BG)
        right.pack(side="right")
        sig = tk.Frame(right, bg=BG)
        sig.pack(anchor="e")
        tk.Label(sig, text="CREATED BY", bg=BG, fg=MUTED, font=self.f_sig).pack(side="left", padx=(0, 6))
        tk.Label(sig, text="XxREPTILExX", bg=BG, fg=SILVER, font=self.f_sig).pack(side="left")
        tk.Label(sig, text="  x  ", bg=BG, fg=EDGE, font=self.f_sig).pack(side="left")
        tk.Label(sig, text="XxNEOPAULxX", bg=BG, fg=TURQ, font=self.f_sig).pack(side="left")

        bar = tk.Frame(self, bg=EDGE, height=1)
        bar.pack(fill="x", padx=16, pady=(8, 0))

    # -- toolbar -------------------------------------------------------------
    def _build_toolbar(self):
        t = tk.Frame(self, bg=BG)
        t.pack(fill="x", padx=16, pady=(10, 6))

        # search
        box = tk.Frame(t, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text=" / ", bg=PANEL, fg=TURQ_DIM, font=self.f_list).pack(side="left", padx=(6, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._on_search())
        self.search = tk.Entry(box, textvariable=self.search_var, bg=PANEL, fg=TEXT,
                               insertbackground=TURQ, relief="flat", font=self.f_body,
                               highlightthickness=0)
        self.search.pack(side="left", fill="x", expand=True, padx=6, pady=5)

        self.btn_reset = tk.Button(t, text="RESET", command=self._clear_all,
                                   bg=PANEL, fg=MUTED, activebackground=EDGE,
                                   activeforeground=TEXT, relief="flat", font=self.f_sig,
                                   padx=10, cursor="hand2")
        self.btn_reset.pack(side="left", padx=(8, 0))

        self.btn_inst = tk.Button(t, text="FOUND ONLY", command=self._toggle_installed,
                                  bg=PANEL, fg=MUTED, activebackground=EDGE,
                                  activeforeground=TEXT, relief="flat", font=self.f_sig,
                                  padx=10, cursor="hand2")
        self.btn_inst.pack(side="left", padx=(6, 0))

        self.btn_rescan = tk.Button(t, text="RESCAN", command=self._rescan,
                                    bg=PANEL, fg=BLUE, activebackground=EDGE,
                                    activeforeground=TEXT, relief="flat", font=self.f_sig,
                                    padx=10, cursor="hand2")
        self.btn_rescan.pack(side="left", padx=(6, 0))

        # flag chips
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(f, text="FLAGS", bg=BG, fg=MUTED, font=self.f_sig).pack(side="left", padx=(2, 8))
        self.chips = {}
        for letter, meaning in FLAG_MEANINGS:
            b = tk.Button(f, text=letter, width=3, command=lambda L=letter: self._toggle_flag(L),
                          bg=PANEL, fg=MUTED, activebackground=EDGE, activeforeground=TEXT,
                          relief="flat", font=self.f_sig, cursor="hand2")
            b.pack(side="left", padx=2)
            self.chips[letter] = b
            self._chip_tip(b, letter + " - " + meaning)

    def _chip_tip(self, widget, text):
        tip = tk.Toplevel(widget)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.configure(bg=EDGE)
        tk.Label(tip, text=text, bg=EDGE, fg=TEXT, font=self.f_small,
                 padx=6, pady=3).pack()

        def enter(_):
            tip.deiconify()
            tip.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip.geometry("+%d+%d" % (x, y))

        def leave(_):
            tip.withdraw()

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")

    # -- body ----------------------------------------------------------------
    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        # left: categories
        left = tk.Frame(body, bg=PANEL, width=196,
                        highlightbackground=EDGE, highlightthickness=1)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="CATEGORIES", bg=PANEL, fg=MUTED, font=self.f_sig).pack(anchor="w", padx=10, pady=(9, 4))
        self.catbox = tk.Listbox(left, bg=PANEL, fg=TEXT, selectbackground="#1B3A52",
                                 selectforeground="#E8F6F4", relief="flat",
                                 highlightthickness=0, font=self.f_list,
                                 activestyle="none", exportselection=False)
        self.catbox.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self.catbox.bind("<<ListboxSelect>>", self._on_cat)

        # right
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        wrap = tk.Frame(right, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        wrap.pack(fill="both", expand=True)

        cols = ("TOOL", "FLAGS", "OS", "STATUS")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 style="Rack.Treeview", selectmode="browse")
        widths = {"TOOL": 360, "FLAGS": 130, "OS": 76, "STATUS": 132}
        for c in cols:
            self.tree.heading(c, text=c, command=lambda cc=c: self._sort(cc))
            self.tree.column(c, width=widths[c], anchor="w" if c == "TOOL" else "center",
                             stretch=(c == "TOOL"))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview,
                           style="Rack.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("found", foreground=TURQ)
        self.tree.tag_configure("weblink", foreground=BLUE)
        self.tree.tag_configure("repo", foreground=SILVER)
        self.tree.tag_configure("manual", foreground=MUTED)
        self.tree.tag_configure("odd", background=PANEL_ALT)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double)

        # detail
        self.detail = tk.Frame(right, bg=PANEL, height=178,
                               highlightbackground=EDGE, highlightthickness=1)
        self.detail.pack(fill="x", pady=(8, 0))
        self.detail.pack_propagate(False)

        self.d_head = tk.Label(self.detail, text="select a tool", bg=PANEL, fg=MUTED,
                               font=self.f_big, anchor="w")
        self.d_head.pack(fill="x", padx=12, pady=(10, 0))

        self.d_text = tk.Text(self.detail, bg=PANEL, fg=TEXT, relief="flat",
                              highlightthickness=0, font=self.f_body, wrap="word",
                              height=6, cursor="arrow")
        self.d_text.pack(fill="both", expand=True, padx=12, pady=(2, 0))
        self.d_text.tag_configure("muted", foreground=MUTED)
        self.d_text.tag_configure("turq", foreground=TURQ)
        self.d_text.tag_configure("blue", foreground=BLUE)
        self.d_text.tag_configure("silver", foreground=SILVER)
        self.d_text.configure(state="disabled")

        btns = tk.Frame(self.detail, bg=PANEL)
        btns.pack(fill="x", padx=12, pady=(0, 10))
        self.b_open = self._dbutton(btns, "OPEN LINK", self._open_link, TURQ)
        self.b_copy = self._dbutton(btns, "COPY LINK", self._copy_link, MUTED)
        self.b_name = self._dbutton(btns, "COPY NAME", self._copy_name, MUTED)
        self.b_cmd = self._dbutton(btns, "COPY CMD", self._copy_cmd, MUTED)

    def _dbutton(self, parent, text, cmd, color):
        b = tk.Button(parent, text=text, command=cmd, bg=PANEL_ALT, fg=color,
                      activebackground=EDGE, activeforeground=TEXT,
                      relief="flat", font=self.f_sig, padx=10, pady=4, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        return b

    def _build_status(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=16, pady=(0, 10))
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=self.f_meta, anchor="w")
        self.status.pack(side="left")
        self.scan_lbl = tk.Label(bar, text="scanning local toolchain ...", bg=BG, fg=BLUE,
                                 font=self.f_meta, anchor="e")
        self.scan_lbl.pack(side="right")

    # -- scanning ------------------------------------------------------------
    def _scan(self):
        """Worker thread: probes only, never touches Tk."""
        found = {}
        for t in TOOLS:
            bins = t.get("b") or []
            if not bins:
                continue
            hit = probe(bins)
            if hit:
                found[t["n"]] = hit
        self._q.put(found)

    def _poll_scan(self):
        try:
            found = self._q.get_nowait()
        except queue.Empty:
            self.after(150, self._poll_scan)
            return
        self._scanning = False
        self._scan_done(found)

    def _scan_done(self, found):
        self.found = found
        self.scan_lbl.configure(
            text="%d of %d tools found on this machine" % (len(found), len(TOOLS)),
            fg=GREEN if found else MUTED)
        self.refresh()

    def _rescan(self):
        if self._scanning:
            return
        self._scanning = True
        self.scan_lbl.configure(text="scanning local toolchain ...", fg=BLUE)
        threading.Thread(target=self._scan, daemon=True).start()
        self.after(150, self._poll_scan)

    # -- filtering -----------------------------------------------------------
    def _status_of(self, t):
        if t["n"] in self.found:
            return "FOUND"
        if "I" in t["f"]:
            return "WEB"
        if "G" in t["f"]:
            return "REPO"
        return "MANUAL"

    def _visible(self):
        q = self.query.lower().strip()
        out = []
        for t in TOOLS:
            if self.active_cat != "ALL" and t["c"] != self.active_cat:
                continue
            if self.active_flags and not self.active_flags.issubset(set(t["f"])):
                continue
            if self.installed_only and t["n"] not in self.found:
                continue
            if q:
                hay = (t["n"] + " " + t["c"] + " " + t["d"] + " " + t["f"]).lower()
                if q not in hay:
                    continue
            out.append(t)
        key = self.sort_col

        def k(t):
            if key == "FLAGS":
                return t["f"]
            if key == "OS":
                return flags_os(t["f"])
            if key == "STATUS":
                return self._status_of(t)
            return t["n"].lower()

        out.sort(key=k, reverse=self.sort_desc)
        return out

    def refresh(self):
        # category counts
        self.catbox.delete(0, "end")
        self.catbox.insert("end", "ALL  (%d)" % len(TOOLS))
        for c in CATEGORIES:
            n = sum(1 for t in TOOLS if t["c"] == c)
            self.catbox.insert("end", "%s  (%d)" % (c, n))
        idx = 0 if self.active_cat == "ALL" else CATEGORIES.index(self.active_cat) + 1
        self.catbox.selection_set(idx)
        self.catbox.see(idx)

        # table
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        rows = self._visible()
        for i, t in enumerate(rows):
            st = self._status_of(t)
            tag = {"FOUND": "found", "WEB": "weblink", "REPO": "repo"}.get(st, "manual")
            iid = self.tree.insert("", "end", values=(
                t["n"], " ".join(t["f"]), flags_os(t["f"]), st), tags=(tag,))
            self.rows[iid] = t
        self._filter_counts()

        self.status.configure(
            text="%d shown / %d total   |   category %s   |   flags %s"
                 % (len(rows), len(TOOLS), self.active_cat,
                    "".join(sorted(self.active_flags)) or "any"))

    def _filter_counts(self):
        for letter, btn in self.chips.items():
            on = letter in self.active_flags
            btn.configure(bg=TURQ_DIM if on else PANEL,
                          fg=BG if on else MUTED,
                          text=letter)

    # -- events --------------------------------------------------------------
    def _on_search(self):
        self.query = self.search_var.get()
        self.refresh()

    def _on_cat(self, _event):
        sel = self.catbox.curselection()
        if not sel:
            return
        val = self.catbox.get(sel[0])
        self.active_cat = "ALL" if val.startswith("ALL") else val.rsplit("  (", 1)[0]
        self.refresh()

    def _toggle_flag(self, letter):
        if letter in self.active_flags:
            self.active_flags.discard(letter)
        else:
            self.active_flags.add(letter)
        self.refresh()

    def _toggle_installed(self):
        self.installed_only = not self.installed_only
        self.btn_inst.configure(bg=TURQ_DIM if self.installed_only else PANEL,
                                fg=BG if self.installed_only else MUTED)
        self.refresh()

    def _clear_all(self, _event=None):
        self.search_var.set("")
        self.query = ""
        self.active_flags.clear()
        self.active_cat = "ALL"
        self.installed_only = False
        self.btn_inst.configure(bg=PANEL, fg=MUTED)
        self.refresh()

    def _sort(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False
        self.refresh()

    def _current(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def _on_select(self, _event):
        t = self._current()
        if not t:
            return
        self.d_head.configure(text=t["n"], fg=TURQ)
        bits = ["%s   |   %s" % (t["c"], flags_os(t["f"]))]
        if t["n"] in self.found:
            bits.append("resolves as: %s" % self.found[t["n"]])
        self.d_text.configure(state="normal")
        self.d_text.delete("1.0", "end")
        self.d_text.insert("end", "  \n".join(bits), "muted")
        self.d_text.insert("end", "\n\n" + t["d"])
        meanings = [m for L, m in FLAG_MEANINGS if L in t["f"]]
        if meanings:
            self.d_text.insert("end", "\n\n", "muted")
            self.d_text.insert("end", "; ".join(meanings), "muted")
        if t.get("u"):
            self.d_text.insert("end", "\n\n", "muted")
            self.d_text.insert("end", t["u"], "blue")
        self.d_text.configure(state="disabled")
        self.b_open.configure(state="normal" if t.get("u") else "disabled")
        self.b_copy.configure(state="normal" if t.get("u") else "disabled")
        self.b_cmd.configure(state="normal" if t.get("x") else "disabled")

    def _on_double(self, _event):
        self._open_link()

    # -- actions -------------------------------------------------------------
    def _open_link(self):
        t = self._current()
        if t and t.get("u"):
            webbrowser.open(t["u"])

    def _clip(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _copy_link(self):
        t = self._current()
        if t and t.get("u"):
            self._clip(t["u"])

    def _copy_name(self):
        t = self._current()
        if t:
            self._clip(t["n"])

    def _copy_cmd(self):
        t = self._current()
        if t and t.get("x"):
            self._clip(t["x"])

    def _quit(self):
        try:
            self.destroy()
        finally:
            os._exit(0)


if __name__ == "__main__":
    _dpi()
    RackJacked().mainloop()
