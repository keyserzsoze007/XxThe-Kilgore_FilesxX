"""XXxVector_SourcingxXX - the OSINT hunter deck: five scout engines, one window (WSL Kali underneath).

Hunts first, breaks later. All findings land in a clickable deck - open, copy,
pivot into another engine, export. Nothing here phones home.
"""
import base64
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import datetime

try:
    import psutil
except Exception:
    psutil = None

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import webbrowser

APP_NAME = "XXxVector_SourcingxXX"
APP_VER = "1.4.2"
CREATORS = ("XxREPTILExX", "XxNEOPAULxX")
DISTRO = "kali-linux"

BG = "#0A0F16"
PANEL = "#0F1723"
PANEL2 = "#131E2C"
PANEL3 = "#182636"
EDGE = "#1C2B3D"
EDGE2 = "#24364E"
TXT = "#C9D6E3"
DIM = "#6B7E93"
TURQ = "#2EE6C8"
BLUE = "#4DA8FF"
RED = "#FF5470"
AMBER = "#FFB454"
GREEN = "#3DDC97"

WSL_EXE = "wsl.exe"
CREATE_NO_WINDOW = 0x08000000

ANSI_RE = re.compile(r"\x1b\[\??[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b\][^\x1b]*(?:\x1b\\)")

DISPLAY_JUNK = ("Inappropriate ioctl", "[?1034h")

ENGINES = {
    "sherlock": {
        "bin": "sherlock", "name": "Sherlock - Usernames",
        "sub": "social accounts by username, 300+ platforms",
        "glyph": "SHL", "color": TURQ,
        "preset": 'sherlock "<username>" --timeout 20',
        "presets": (
            'sherlock "<username>" --timeout 20',
            'sherlock "<username>" --timeout 20 --print-found',
            'sherlock "<username>"',
        ),
        "ph": "<username>", "pivot_hint": "username",
    },
    "harv": {
        "bin": "theHarvester", "name": "theHarvester - Domains",
        "sub": "emails / hosts / people from public sources",
        "glyph": "HRV", "color": BLUE,
        "preset": 'theHarvester -d "<domain>" -b crtsh,otx,duckduckgo,hackertarget',
        "presets": (
            'theHarvester -d "<domain>" -b crtsh,otx,duckduckgo,hackertarget',
            'theHarvester -d "<domain>" -b crtsh,otx',
            'theHarvester -d "<domain>" -b duckduckgo',
        ),
        "ph": "<domain>", "pivot_hint": "domain",
    },
    "amass": {
        "bin": "amass", "name": "Amass - Assets",
        "sub": "deep attack-surface mapping (passive)",
        "glyph": "AMS", "color": TURQ,
        "preset": 'amass enum -d "<domain>"',
        "presets": (
            'amass enum -d "<domain>"',
            'amass enum -d "<domain>" -src',
            'amass enum -d "<domain>" -ip',
        ),
        "ph": "<domain>", "pivot_hint": "domain",
    },
    "exif": {
        "bin": "exiftool", "name": "ExifTool - Metadata",
        "sub": "every hidden field in images / PDFs / docs",
        "glyph": "EXF", "color": BLUE,
        "preset": 'exiftool "<file>"',
        "presets": (
            'exiftool "<file>"',
            'exiftool -a -G1 "<file>"',
            'exiftool -a -u -g1 "<file>"',
        ),
        "ph": "<file>", "pivot_hint": "file",
    },
    "leaks": {
        "bin": "gitleaks", "name": "Gitleaks - Secrets",
        "sub": "api keys / passwords hiding in repos",
        "glyph": "GLK", "color": TURQ,
        "preset": 'gitleaks dir "<target-dir>" --verbose',
        "presets": (
            'gitleaks dir "<target-dir>" --verbose',
            'gitleaks git "<repo-dir>" --verbose',
        ),
        "ph": "<target-dir>", "pivot_hint": "directory",
    },
    "whois": {
        "bin": "whois", "name": "Whois - Registry",
        "sub": "registry facts for a domain (quick lane)",
        "glyph": "WHS", "color": BLUE,
    },
    "dig": {
        "bin": "dig", "name": "Dig - DNS",
        "sub": "live DNS records for a domain (quick lane)",
        "glyph": "DNS", "color": TURQ,
    },
}
ENGINE_ORDER = ["sherlock", "harv", "amass", "exif", "leaks"]

INSTALL_PKGS = "sherlock gitleaks"

PROBE_SCRIPT = (
    "for b in sherlock theHarvester amass exiftool gitleaks; do "
    "if command -v \"$b\" >/dev/null 2>&1; then "
    "v=$(\"$b\" --version 2>/dev/null | grep -Eo '[0-9]+\\.[0-9][0-9.]*' | head -n1); "
    "[ -z \"$v\" ] && v=$(\"$b\" -ver 2>/dev/null | head -n1); "
    "[ -z \"$v\" ] && v=detected; "
    "echo \"$b|$v\"; else echo \"$b|MISSING\"; fi; done"
)


def b64(payload):
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def shq(s):
    return "'" + s.replace("'", "'\\''") + "'"


def to_wsl_path(p):
    p = os.path.abspath(p)
    drive, rest = os.path.splitdrive(p)
    d = drive[0].lower()
    rest = rest.replace("\\", "/")
    return "/mnt/" + d + rest


def run_wsl_b64(script, timeout=90):
    cmd = [WSL_EXE, "-d", DISTRO, "-u", "root", "--", "bash", "-lc",
           "echo " + b64(script) + " | base64 -d | bash"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception as e:
        return -1, "probe error: %s" % e


def res_path(rel):
    base = getattr(sys, "_MEIPASS", None)
    if base and os.path.exists(os.path.join(base, rel)):
        return os.path.join(base, rel)
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    cand = os.path.join(here, rel)
    if os.path.exists(cand):
        return cand
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


def app_data_dir():
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    logs = os.path.join(here, "logs")
    try:
        os.makedirs(logs, exist_ok=True)
        t = os.path.join(logs, ".w")
        with open(t, "w") as f:
            f.write("ok")
        os.remove(t)
        return logs
    except Exception:
        logs = os.path.join(os.environ.get("APPDATA", here), APP_NAME, "logs")
        os.makedirs(logs, exist_ok=True)
        return logs


def blend(c1, c2, f):
    a = int(c1.lstrip("#"), 16)
    b = int(c2.lstrip("#"), 16)
    r = int(((a >> 16) & 255) * f + ((b >> 16) & 255) * (1 - f))
    g = int(((a >> 8) & 255) * f + ((b >> 8) & 255) * (1 - f))
    bl = int((a & 255) * f + (b & 255) * (1 - f))
    return "#%02x%02x%02x" % (r, g, bl)


def fmt_bytes(v):
    v = max(0.0, float(v))
    for u in ("B", "KB", "MB", "GB"):
        if v < 1024 or u == "GB":
            return "%.0f %s" % (v, u)
        v /= 1024.0


def mask_secret(s):
    s = s.strip()
    if len(s) <= 6:
        return "*" * len(s)
    return s[:3] + "*" * max(4, len(s) - 6) + s[-3:]


# ---------------------------------------------------------------------------
# live parsers - turn engine streams into deck rows as they arrive
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://\S+")
FQDN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}[.:]?$")
GPS_DEG_RE = re.compile(
    r"(-?\d+(?:\.\d+)?) deg (\d+)' (\d+(?:\.\d+)?)\" ([NSEW])")


class ParserState:
    def __init__(self):
        self.hrv_type = None
        self.leak = None
        self.lat = None
        self.lon = None
        self.seen_urls = set()


def _flush_leak(state, emit):
    r = state.leak
    state.leak = None
    if r and (r.get("secret") or r.get("rule")):
        loc = ":".join([r.get("file", ""), r.get("line", "")]).strip(":")
        emit("leaks", r.get("rule", "SECRET"),
             loc or "(memory)",
             mask_secret(r.get("secret", "") or "?"),
             secret=r.get("secret"))


def parse_line(key, line, state, emit):
    """Feed one clean output line; emit deck rows (eng, find, val, det, **attrs)."""
    s = line.strip()
    if not s:
        return
    if key == "sherlock":
        m = re.match(r"^\[\+\]\s*(?!Found\b|Target\b|User\b)"
                     r"([A-Za-z0-9 .&!?'\-]+?):\s*(https?://\S+)\s*$", s)
        if m:
            url = m.group(2)
            if url not in state.seen_urls:
                state.seen_urls.add(url)
                emit("sherlock", m.group(1).strip(), url, "FOUND", url=url)
            return
        m = re.match(r"^\[[+*!]\]\s*(?:Found:?\s*)?(https?://\S+?)(?:\s*\(([^)]*)\))?\s*$", s)
        if m is None:
            m = re.match(r"^\(\+\d+\)\s*(https?://\S+?)(?:\s*\(([^)]*)\))?\s*$", s)
        if m:
            url = m.group(1).rstrip("),")
            code = (m.group(2) or "").strip()
            if url in state.seen_urls:
                return
            state.seen_urls.add(url)
            host = URL_RE.match(url).group(0).split("/")[2].lower()
            emit("sherlock", host.split(".")[-2] if "." in host else host,
                 url, code or "FOUND", url=url)
            return
        mm = re.match(r"^\[[+*]\]\s*(?:Target|User(?:name)?|Checking (?:username )?):?\s*(\S+?)(?:\s+on:?)?\s*$",
                      s, re.I)
        if mm:
            emit("sherlock", "TARGET", mm.group(1), "")
            return
    elif key == "harv":
        mt = re.match(r"^\[\*\]\s*(?:Target|Domain):?\s*(\S+)\s*$", s, re.I)
        if mt:
            state.hrv_type = None
            emit("harv", "TARGET", mt.group(1), "")
            return
        m = re.match(r"^\[\+?\]?\s*([A-Za-z]+)s?\s+found:\s*(\S.*)$", s, re.I)
        if m and not m.group(2).strip().isdigit():
            emit("harv", m.group(1).upper(), m.group(2).strip(), "")
            return
        if m:
            state.hrv_type = m.group(1).upper()
            return
        mm = re.match(r"^\s*(?:\[[^\]]*\]\s*)?(?:[-=*\s]{3,}\s*)?([A-Za-z]+)s?\s+"
                      r"found\b[^A-Za-z]*$", s, re.I)
        if mm:
            state.hrv_type = mm.group(1).upper()
            return
        if state.hrv_type and not re.match(r"^\s*[*=\-]{3,}", s) \
                and not re.match(r"^\s*\[[^\]]*\]", s) \
                and not re.match(r"^\s*No\s+\w+\s+found", s, re.I):
            t = state.hrv_type
            if t == "PEOPLE" and re.match(r"^[A-Za-z.\' -]+$", s):
                emit("harv", t, s, "")
            elif " " not in s and ("@" in s or "." in s or any(c.isdigit() for c in s)
                                   or s.lower() == "unavailable") and len(s) < 200:
                emit("harv", t, s, "")
    elif key == "amass":
        if s.startswith("["):
            return
        if re.match(r"^\d+\s*/\s*\d+\s*\[", s):
            return
        if FQDN_RE.match(s) and s.count(".") >= 1:
            emit("amass", "ASSET", s.rstrip(".:"), "")
    elif key == "exif":
        if s.startswith(("========", "  0 image", "1 director", "image files")):
            _flush_gps(state, emit)
            return
        if " : " in s:
            k, v = s.split(" : ", 1)
            k = k.strip().lstrip("| ").strip()
            v = v.strip()
            if not k or len(k) > 60:
                return
            grp = ""
            mgrp = re.match(r"^\[([A-Za-z0-9 _]+)\]\s+(.*)$", k)
            if mgrp:
                grp, k = mgrp.group(1), mgrp.group(2).strip()
            kl = k.lower()
            gps_all = GPS_DEG_RE.findall(v)
            if kl.startswith("gps position") and len(gps_all) >= 2:
                state.lat = _deg_to_dec(gps_all[0])
                state.lon = _deg_to_dec(gps_all[1])
            elif kl.startswith("gps latitude") and gps_all:
                state.lat = _deg_to_dec(gps_all[0])
            elif kl.startswith("gps longitude") and gps_all:
                state.lon = _deg_to_dec(gps_all[0])
            emit("exif", k, v, grp)
    elif key == "leaks":
        low = s.strip()
        if low.startswith("Finding:"):
            _flush_leak(state, emit)
            state.leak = {}
            return
        if state.leak is None:
            return
        if low.startswith("Secret:"):
            state.leak["secret"] = low.split(":", 1)[1].strip()
        elif low.startswith("RuleID:"):
            state.leak["rule"] = low.split(":", 1)[1].strip()
        elif low.startswith("File:"):
            state.leak["file"] = low.split(":", 1)[1].strip()
        elif low.startswith("Line:"):
            state.leak["line"] = low.split(":", 1)[1].strip()
    elif key == "whois":
        seen = getattr(state, "lane_seen", None)
        if seen is None:
            seen = set()
            state.lane_seen = seen
        m = re.match(r"^([A-Z][A-Za-z0-9 ()/.-]{2,40}?)\s*:\s*(\S.*)$", s)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            kl = k.lower()
            if any(t in kl for t in ("registrar name", "registrar", "creation date",
                                     "created date", "updated date", "expiry date",
                                     "expiration date", "name server",
                                     "domain status", "registrant organization",
                                     "registrant country", "registry expiry")):
                pair = (k, v)
                if pair not in seen:
                    seen.add(pair)
                    emit("whois", k, v[:600], "")
    elif key == "dig":
        m = re.match(r"^(\S+)\s+\d+\s+IN\s+(\S+)\s+(.+)$", s)
        if m:
            emit("dig", m.group(2), m.group(3).strip()[:600], m.group(1))


def _deg_to_dec(gp):
    if hasattr(gp, "groups") and callable(gp.groups):
        gp = gp.groups()
    try:
        deg, mn, sec, hemi = gp
        v = float(deg) + float(mn) / 60.0 + float(sec) / 3600.0
        if hemi in ("S", "W"):
            v = -v
        return v
    except Exception:
        return None


def _flush_gps(state, emit):
    if state.lat and state.lon:
        q = "%.6f,%.6f" % (state.lat, state.lon)
        emit("exif", "GPS COORDS", q, "open map",
             url="https://maps.google.com/?q=" + q)
    state.lat = None
    state.lon = None


def file_flush(key, state, emit):
    if key == "leaks":
        _flush_leak(state, emit)
    if key == "exif":
        _flush_gps(state, emit)


class Job:
    def __init__(self, key, cmdline, ctx):
        self.key = key
        self.cmdline = cmdline
        self.ctx = ctx
        self.state = ParserState()
        self.t0 = time.time()
        self.proc = None
        self.stopped = False
        self.rc = None
        self.log = open(os.path.join(ctx.logs_dir, "%s-%s.log" % (
            key, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))), "a", encoding="utf-8")
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        cmdline = self.cmdline
        cmd = [WSL_EXE, "-d", DISTRO, "-u", "root", "--", "bash", "-lc",
               "cd /tmp && " + cmdline]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                                         creationflags=CREATE_NO_WINDOW)
        except Exception as e:
            self.rc = -1
            self.ctx.put(("out", self.key, "LAUNCH ERROR: %s\n" % e))
            self.ctx.put(("exit", self.key, -1))
            return
        self.thread.start()

    def _run(self):
        try:
            while True:
                chunk = self.proc.stdout.read(4096)
                if not chunk:
                    break
                self.ctx.put(("out", self.key, chunk.decode("utf-8", "replace")))
                try:
                    self.log.write(chunk.decode("utf-8", "replace"))
                    self.log.flush()
                except Exception:
                    pass
        except Exception as e:
            self.ctx.put(("out", self.key, "\n[reader: %s]\n" % e))
        try:
            self.rc = self.proc.wait(timeout=10)
        except Exception:
            self.rc = -9
        try:
            self.log.close()
        except Exception:
            pass
        self.ctx.put(("exit", self.key, self.rc))

    def stop(self):
        self.stopped = True
        try:
            self.proc.terminate()
        except Exception:
            pass
        binname = ENGINES[self.key]["bin"]
        script = "pkill -TERM -f %s 2>/dev/null; sleep 0.5; pkill -KILL -f %s 2>/dev/null; true" % (
            binname, binname)
        threading.Thread(target=lambda: run_wsl_b64(script, 20), daemon=True).start()

    def send(self, text):
        proc = self.proc
        if not (proc and proc.stdin and proc.poll() is None):
            return False
        try:
            proc.stdin.write((text.rstrip("\r\n") + "\n").encode("utf-8", "replace"))
            proc.stdin.flush()
            return True
        except Exception:
            return False


class Gauge(tk.Canvas):
    def __init__(self, parent, label, color, fmt="%.0f%%", fmtfn=None):
        super().__init__(parent, width=104, height=150, bg=PANEL, highlightthickness=0)
        self.label = label
        self.color = color
        self.fmt = fmt
        self.fmtfn = fmtfn
        self.display = 0.0
        self.tgt = 0.0
        self.raw = 0.0
        self.onpaint()

    def set(self, v):
        self.tgt = max(0.0, float(v))

    def set_raw(self, v):
        self.raw = max(0.0, float(v))

    def tick(self):
        self.display += (self.tgt - self.display) * 0.30
        if abs(self.tgt - self.display) < 0.05:
            self.display = self.tgt
        self.onpaint()

    def onpaint(self):
        c = self
        c.delete("all")
        w, h = 104, 150
        frac = max(0.0, min(1.0, self.display / 100.0 if self.fmt == "%.0f%%" else
                            min(1.0, self.display / max(1.0, self.tgt * 1.25))))
        bx, bw = 28, 26
        bt, bb = 30, h - 34
        c.create_rectangle(bx - 6, bt - 6, bx + bw + 6, bb + 6, outline=EDGE2)
        c.create_rectangle(bx, bt, bx + bw, bb, fill=PANEL2, outline="")
        bh = (bb - bt) * frac
        steps = max(1, int(bh) // 4)
        for i in range(steps):
            y0 = bb - bh * (i / float(steps))
            y1 = bb - bh * ((i + 1) / float(steps))
            f = 0.35 + 0.55 * (i / float(steps or 1))
            c.create_rectangle(bx, int(y0), bx + bw, int(y1),
                               fill=blend(self.color, PANEL2, f), outline="")
        for i in range(5):
            y = bt + (bb - bt) * i / 4.0
            c.create_line(bx + bw + 2, y, bx + bw + 9, y, fill=EDGE)
        c.create_text(w // 2, 14, text=self.label, fill=DIM, font=("Segoe UI", 8, "bold"))
        val = self.fmtfn(self.raw) if self.fmtfn else self.fmt % self.display
        c.create_text(w // 2, h - 13, text=val, fill=TXT, font=("Consolas", 11, "bold"))


class Sparkline(tk.Canvas):
    def __init__(self, parent, color):
        super().__init__(parent, width=520, height=150, bg=PANEL, highlightthickness=0)
        self.color = color
        self.data = [0.0] * 130
        self.peak = 1.0

    def tick(self, v):
        self.data.append(max(0.0, float(v)))
        self.data = self.data[-130:]
        mx = max(self.data)
        if mx > self.peak or mx < self.peak * 0.05:
            self.peak = max(1.0, mx)
        self.onpaint()

    def onpaint(self):
        c = self
        c.delete("all")
        w = max(300, int(c.winfo_width()) or 520)
        h = 150
        top, bottom = 26, h - 22
        for i in range(1, 5):
            y = top + (bottom - top) * i / 4.0
            c.create_line(42, y, w - 12, y, fill=EDGE, dash=(2, 4))
        step = (w - 54) / float(len(self.data) - 1 or 1)
        poly = []
        for i, v in enumerate(self.data):
            x = 42 + i * step
            y = bottom - (bottom - top) * (v / self.peak)
            poly.append((x, y))
        if len(poly) > 1:
            c.create_polygon([(42, bottom)] + poly + [(poly[-1][0], bottom)],
                             fill=blend(self.color, BG, 0.16), outline="")
            c.create_line(poly, fill=self.color, width=2, smooth=True)
        c.create_text(w // 2, 10, text="HUNT OUTPUT RATE", fill=DIM,
                      font=("Segoe UI", 8, "bold"))
        c.create_text(w - 66, top, text="peak %s/s" % fmt_bytes(self.peak), fill=DIM,
                      font=("Consolas", 8))


class RailTab(tk.Frame):
    """Vertical hunter tab - different DNA from the old tiles."""

    def __init__(self, parent, ctx, key):
        super().__init__(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=EDGE, cursor="hand2")
        self.ctx = ctx
        self.key = key
        t = ENGINES[key]
        self.status_kind = "idle"
        self.ver = ""
        self.elapsed = ""
        self.rc = None
        self.phase = 0.0
        self.count = 0

        row = tk.Frame(self, bg=PANEL)
        row.pack(fill="x", padx=9, pady=7)
        cv = tk.Canvas(row, width=34, height=34, bg=PANEL, highlightthickness=0)
        cv.create_oval(2, 2, 32, 32, fill=t["color"])
        cv.create_text(17, 17, text=t["glyph"], fill=BG, font=("Consolas", 8, "bold"))
        cv.pack(side="left")
        rb = tk.Frame(row, bg=PANEL)
        rb.pack(side="left", fill="x", expand=True, padx=(9, 0))
        tk.Label(rb, text=t["name"], bg=PANEL, fg=TXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(rb, text=t["sub"], bg=PANEL, fg=DIM, font=("Segoe UI", 7)).pack(anchor="w")
        bch = tk.Frame(self, bg=PANEL)
        bch.pack(fill="x", padx=9, pady=(0, 7))
        self.chip = tk.Label(bch, text="", bg=PANEL, fg=DIM,
                             font=("Consolas", 8, "bold"), anchor="w")
        self.chip.pack(side="left")
        self.badge = tk.Label(bch, text="0", bg=PANEL2, fg=DIM,
                              font=("Consolas", 8, "bold"), padx=7)
        self.badge.pack(side="right")
        self.bind("<Button-1>", self._click)
        for w in self.winfo_children():
            self._deepbind(w)
        self._paint_chip()

    def _deepbind(self, w):
        w.bind("<Button-1>", self._click)
        for kid in w.winfo_children():
            self._deepbind(kid)

    def _click(self, e):
        self.ctx.select_engine(self.key)

    def paint(self):
        self.phase += 0.10
        if self.status_kind == "run":
            p = 0.5 + 0.5 * ((self.phase % (2 * 3.14159265)) / (2 * 3.14159265))
            edge = blend(TURQ, BLUE, p * 0.6)
        elif self.status_kind == "done":
            edge = GREEN
        elif self.status_kind == "fail":
            edge = RED
        elif self.status_kind == "stopped":
            edge = AMBER
        elif self.status_kind == "missing":
            edge = blend(RED, EDGE, 0.6)
        else:
            edge = EDGE
        self.configure(highlightbackground=edge, highlightcolor=edge)
        self._paint_chip()

    def _paint_chip(self):
        t = ENGINES[self.key]
        m = {
            "detect": (GREEN, "DETECTED"),
            "missing": (RED, "MISSING"),
            "run": (TURQ, "RUNNING"),
            "done": (GREEN, "EXIT 0"),
            "stopped": (AMBER, "STOPPED"),
            "fail": (RED, "EXIT %d" % (self.rc if self.rc else -1)),
            "probe": (DIM, "CHECKING..."),
            "idle": (DIM, ""),
        }
        col, txt = m.get(self.status_kind, (DIM, ""))
        parts = [t["bin"], txt]
        if self.status_kind == "run":
            parts.append(self.elapsed)
        elif self.status_kind == "detect" and self.ver:
            parts = [t["bin"], self.ver[:30]]
        self.chip.configure(fg=col, text=" ".join(x for x in parts if x))
        self.badge.configure(fg=(TXT if self.count else DIM),
                             bg=(blend(t["color"], BG, 0.78) if self.count else PANEL2))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s" % (APP_NAME, APP_VER))
        self.configure(bg=BG)
        self.geometry("1400x%d" % min(860, max(700, self.winfo_screenheight() - 64)))
        self.minsize(1200, 700)
        self._alive = True
        self.probe_running = False

        self.logs_dir = app_data_dir()
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_log = open(os.path.join(self.logs_dir, "session-%s.log" % stamp),
                                "a", encoding="utf-8")
        self.q = queue.Queue()
        self.jobs = {}
        self.selected = ENGINE_ORDER[0]
        self.out_bytes = 0
        self.lines_out = 0
        self._last_bytes = 0

        self.find_rows = {}
        self.find_rows_seq = 0
        self.find_counts = {k: 0 for k in ENGINE_ORDER}
        self.deck_filter = "all"
        self.deck_search = ""

        self._build()
        self._style_combos()
        self.sysmsg("%s %s - created by %s & %s" % (
            APP_NAME, APP_VER, CREATORS[0], CREATORS[1]))
        self.sysmsg("hunt first. break later. nothing here phones home.")
        self.select_engine(self.selected)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(400, self.probe_engines)
        self.after(900, self._tick_sensors)
        self.after(80, self._drain)
        self.after(60, self._tick_ui)

    def put(self, item):
        self.q.put(item)

    def _on_close(self):
        self._alive = False
        for j in list(self.jobs.values()):
            try:
                j.stop()
            except Exception:
                pass
        try:
            self.session_log.write("\n[session closed %s]\n" % datetime.datetime.now())
            self.session_log.close()
        except Exception:
            pass
        self.destroy()

    # ---------------------------------------------------------------- build
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        head = tk.Frame(self, bg=PANEL, height=64)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 6))
        head.grid_propagate(False)
        logo = tk.Canvas(head, width=44, height=44, bg=PANEL, highlightthickness=0)
        logo.create_oval(3, 3, 41, 41, outline=TURQ, width=2)
        logo.create_oval(11, 11, 33, 33, outline=EDGE2, width=2)
        logo.create_oval(19, 19, 25, 25, fill=TURQ, outline="")
        logo.create_line(22, 0, 22, 8, fill=TURQ)
        logo.create_line(22, 36, 22, 44, fill=TURQ)
        logo.create_line(0, 22, 8, 22, fill=TURQ)
        logo.create_line(36, 22, 44, 22, fill=TURQ)
        logo.pack(side="left", padx=(10, 12))
        tt = tk.Frame(head, bg=PANEL)
        tt.pack(side="left")
        tk.Label(tt, text="XXxVector_SourcingxXX", bg=PANEL, fg=TXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        sig = tk.Frame(tt, bg=PANEL)
        sig.pack(anchor="w")
        tk.Label(sig, text="CREATED BY", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Label(sig, text=" " + CREATORS[0] + " ", bg=PANEL, fg=TXT,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(sig, text="&", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(sig, text=" " + CREATORS[1] + " ", bg=PANEL, fg=TURQ,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(tt, text="five scouts. one hunt deck. kali linux underneath.",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")

        self.live_chip = tk.Label(head, text="STANDBY", bg=PANEL2, fg=DIM,
                                  font=("Consolas", 9, "bold"), padx=12, pady=4)
        self.live_chip.pack(side="right", padx=(0, 12))
        self.wsl_btn = tk.Label(head, text="WSL CONSOLE", bg=PANEL2, fg=BLUE,
                                font=("Consolas", 9, "bold"), padx=10, pady=4, cursor="hand2")
        self.wsl_btn.pack(side="right", padx=(0, 8))
        self.wsl_btn.bind("<Button-1>", lambda e: self.open_wsl_console())

        rail = tk.Frame(self, bg=BG, width=300)
        rail.grid(row=1, column=0, sticky="nsew", padx=(14, 6))
        rail.pack_propagate(False)
        tk.Label(rail, text="THE HUNTERS", bg=BG, fg=DIM,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 6))
        self.tabs = {}
        for k in ENGINE_ORDER:
            tab = RailTab(rail, self, k)
            tab.pack(fill="x", pady=4, ipady=1)
            self.tabs[k] = tab
        self.repair_btn = tk.Label(rail, text="PULL MISSING SCOUTS", bg=PANEL2, fg=BLUE,
                                   font=("Consolas", 9, "bold"), padx=8, pady=8, cursor="hand2")
        self.repair_btn.pack(fill="x", pady=(12, 4))
        self.repair_btn.bind("<Button-1>", lambda e: self.install_engines())
        self.ledger = tk.Label(rail, text="", bg=BG, fg=DIM, font=("Segoe UI", 8, "italic"),
                               anchor="w", justify="left")
        self.ledger.pack(fill="x", side="bottom", pady=6)

        right = tk.Frame(self, bg=BG)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 14))
        right.rowconfigure(1, weight=4)
        right.rowconfigure(2, weight=3)
        right.columnconfigure(0, weight=1)

        bar = tk.Frame(right, bg=PANEL)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(bar, text=" SCOUT", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=8)
        self.toolvar = tk.StringVar(value=ENGINES[self.selected]["name"])
        self.toolbox = ttk.Combobox(bar, textvariable=self.toolvar, state="readonly",
                                    values=[ENGINES[k]["name"] for k in ENGINE_ORDER], width=11)
        self.toolbox.pack(side="left", padx=(4, 0), pady=8)
        self.toolbox.bind("<<ComboboxSelected>>", lambda e: self._on_toolbox())
        tk.Label(bar, text="  TARGET", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.targetvar = tk.StringVar()
        self.target_entry = tk.Entry(bar, textvariable=self.targetvar, width=16,
                                     bg=PANEL2, fg=AMBER, insertbackground=AMBER,
                                     relief="flat", font=("Consolas", 10))
        self.target_entry.pack(side="left", padx=(4, 0), pady=8)
        self.target_entry.bind("<Return>", lambda e: self.run_selected())
        self.targetvar.trace_add("write", lambda *a: self._on_target())
        tk.Label(bar, text="  COMMAND", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.cmdvar = tk.StringVar(value=ENGINES[self.selected]["preset"])
        self.cmdbox = ttk.Combobox(bar, textvariable=self.cmdvar, width=44)
        self.cmdbox.pack(side="left", fill="x", expand=True, padx=(4, 4), pady=8)
        self.browse_btn = tk.Label(bar, text=" BROWSE ", bg=PANEL2, fg=TURQ,
                                   font=("Consolas", 9, "bold"), padx=8, pady=5,
                                   cursor="hand2")
        self.browse_btn.pack(side="left", pady=8)
        self.browse_btn.bind("<Button-1>", lambda e: self.browse_target())
        self.run_btn = tk.Label(bar, text=" RUN ", bg=blend(TURQ, BG, 0.82), fg=BG,
                                font=("Consolas", 11, "bold"), padx=16, pady=5, cursor="hand2")
        self.run_btn.pack(side="left", padx=2)
        self.run_btn.bind("<Button-1>", lambda e: self.run_selected())
        self.stop_btn = tk.Label(bar, text=" STOP ", bg=PANEL2, fg=DIM,
                                 font=("Consolas", 11, "bold"), padx=14, pady=5, cursor="hand2")
        self.stop_btn.pack(side="left", padx=(2, 10))
        self.stop_btn.bind("<Button-1>", lambda e: self.stop_selected())
        self.full_btn = tk.Label(bar, text=" FULL SCREEN ", bg=PANEL2, fg=TURQ,
                                 font=("Consolas", 10, "bold"), padx=10, pady=5,
                                 cursor="hand2")
        self.full_btn.pack(side="left", padx=(2, 12))
        self.full_btn.bind("<Button-1>", lambda e: self._toggle_full())

        stages = tk.Frame(right, bg=PANEL)
        stages.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        tk.Label(stages, text=" FLOW", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=8)
        self.stage_lamps = {}
        for i, k in enumerate(ENGINE_ORDER):
            nm = ENGINES[k]["name"].split(" - ")[0].upper()
            lamp = tk.Label(stages, text=" %d %s " % (i + 1, nm[:8]),
                            bg=PANEL2, fg=DIM, font=("Consolas", 9, "bold"),
                            padx=7, pady=4)
            lamp.pack(side="left", padx=(6, 0), pady=8)
            self.stage_lamps[k] = lamp

        deckwrap = tk.Frame(right, bg=EDGE2, highlightthickness=1, highlightbackground=EDGE2)
        deckwrap.grid(row=1, column=0, sticky="nsew")
        deckwrap.columnconfigure(0, weight=1)
        deckwrap.rowconfigure(1, weight=1)
        dhead = tk.Frame(deckwrap, bg=PANEL)
        dhead.grid(row=0, column=0, sticky="ew")
        tk.Label(dhead, text=" FINDINGS DECK", bg=PANEL, fg=TURQ,
                 font=("Segoe UI", 10, "bold")).pack(side="left", pady=6)
        self.filter_chips = {}
        for label, val in (("ALL", "all"),
                            ("SHL", "sherlock"), ("HRV", "harv"),
                            ("AMS", "amass"), ("EXF", "exif"), ("GLK", "leaks")):
            chip = tk.Label(dhead, text=" %s " % label,
                            bg=PANEL2, fg=(BG if val == "all" else DIM),
                            font=("Consolas", 8, "bold"), padx=6, pady=3, cursor="hand2")
            chip.pack(side="left", padx=(5, 0))
            chip.bind("<Button-1>", lambda e, v=val: self.set_deck_filter(v))
            self.filter_chips[val] = chip
        tk.Label(dhead, text="FILTER", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(12, 3))
        self.searchvar = tk.StringVar()
        self.searchbox = tk.Entry(dhead, textvariable=self.searchvar, bg=PANEL2, fg=TXT,
                                  insertbackground=TURQ, relief="flat", width=18,
                                  font=("Consolas", 9), highlightthickness=1,
                                  highlightbackground=EDGE2, highlightcolor=TURQ)
        self.searchbox.pack(side="left", pady=6)
        self.searchbox.bind("<KeyRelease>", lambda e: self.set_deck_search())
        self.exp_btn = tk.Label(dhead, text=" EXPORT ", bg=PANEL2, fg=TURQ,
                                font=("Consolas", 9, "bold"), padx=8, pady=3, cursor="hand2")
        self.exp_btn.pack(side="right", padx=(6, 10))
        self.exp_btn.bind("<Button-1>", lambda e: self.export_deck())
        self.clear_btn = tk.Label(dhead, text=" CLEAR ", bg=PANEL2, fg=RED,
                                  font=("Consolas", 9, "bold"), padx=8, pady=3, cursor="hand2")
        self.clear_btn.pack(side="right", padx=6)
        self.clear_btn.bind("<Button-1>", lambda e: self.clear_deck(confirm=True))
        self.deck_chip = tk.Label(dhead, text="0 findings", bg=PANEL, fg=DIM,
                                  font=("Consolas", 8))
        self.deck_chip.pack(side="right")

        decksplit = tk.Frame(deckwrap, bg=PANEL)
        decksplit.grid(row=1, column=0, sticky="nsew")
        decksplit.rowconfigure(0, weight=1)
        decksplit.columnconfigure(0, weight=5, minsize=560)
        decksplit.columnconfigure(1, weight=4, minsize=400)

        deckbody = tk.Frame(decksplit, bg=PANEL)
        deckbody.grid(row=0, column=0, sticky="nsew")
        self.deck = ttk.Treeview(deckbody, columns=("eng", "find", "val", "det"),
                                 show="headings", style="Deck.Treeview",
                                 selectmode="browse")
        for cid, txt, w, stretch in (
                ("eng", "SCOUT", 92, True), ("find", "FINDING", 190, True),
                ("val", "VALUE", 380, True), ("det", "DETAIL", 220, True)):
            self.deck.heading(cid, text=txt)
            self.deck.column(cid, width=w, anchor="w", stretch=stretch)
        vsb = ttk.Scrollbar(deckbody, command=self.deck.yview)
        hsb = ttk.Scrollbar(deckbody, orient="horizontal", command=self.deck.xview)
        self.deck.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(fill="y", side="right")
        self.deck.pack(side="left", fill="both", expand=True)
        self.deck.bind("<MouseWheel>", self._deck_wheel, add="+")
        self.deck.bind("<Shift-MouseWheel>", self._deck_wheel, add="+")
        self.deck.bind("<Button-1>", self._on_deck_release)
        self.deck.bind("<Double-1>", lambda e: self._viewer_open())
        self.deck.bind("<<TreeviewSelect>>", lambda e: self._inspect_fill())

        viewwrap = tk.Frame(decksplit, bg=PANEL2, highlightthickness=1,
                            highlightbackground=EDGE2)
        viewwrap.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        viewwrap.rowconfigure(2, weight=1)
        viewwrap.columnconfigure(0, weight=1)
        viewhead = tk.Frame(viewwrap, bg=PANEL2)
        viewhead.grid(row=0, column=0, sticky="ew")
        tk.Label(viewhead, text=" FINDING CONTENT", bg=PANEL2, fg=TURQ,
                 font=("Segoe UI", 10, "bold")).pack(side="left", pady=5)
        self.view_chip = tk.Label(viewhead, text="double-click a finding -",
                                  bg=PANEL2, fg=DIM, font=("Consolas", 8))
        self.view_chip.pack(side="right", padx=6)
        self._view_row = None
        self._view_rawline = False
        vbtn = tk.Frame(viewwrap, bg=PANEL2)
        vbtn.grid(row=1, column=0, sticky="ew")
        for strip, defs in (
                (0, ((" OPEN ", self._view_open, TURQ),
                     (" UNMASK ", self._view_reveal, AMBER),
                     (" RAW LINE ", self._view_raw, AMBER),
                     (" PIVOT ", self._view_pivot, BLUE))),
                (1, ((" COPY VAL ", self._view_copy_val, GREEN),
                     (" COPY FULL ", self._view_copy_full, GREEN),
                     (" WHOIS ", lambda: self._view_lane("whois"), BLUE),
                     (" DIG ", lambda: self._view_lane("dig"), BLUE)))):
            rowf = tk.Frame(vbtn, bg=PANEL2)
            rowf.pack(side="top", fill="x")
            for label, fn, fg in defs:
                b = tk.Label(rowf, text=label, bg=PANEL, fg=fg,
                             font=("Consolas", 8, "bold"), padx=7, pady=3,
                             cursor="hand2")
                b.pack(side="left", padx=(5, 0), pady=3)
                b.bind("<Button-1>", lambda e, f=fn: f())
        self.viewer = tk.Text(viewwrap, bg=PANEL, fg=TXT, wrap="char",
                              bd=0, padx=10, pady=8, font=("Consolas", 10),
                              relief="flat", state="disabled", takefocus=0,
                              height=4)
        self.viewer.grid(row=2, column=0, sticky="nsew")
        self.viewer.configure(state="normal")
        self.viewer.insert("1.0", " click or double-click a finding -\n its full content opens here")
        self.viewer.configure(state="disabled")

        hint = tk.Label(deckwrap, text=" click a finding: content lands on the right "
                        "panel  -  double-click: full content + one-click actions "
                        " OPEN / UNMASK / RAW LINE / PIVOT / COPY / WHOIS / DIG  "
                        "-  FULL SCREEN button (top bar) grows the window",
                        bg=PANEL, fg=DIM, font=("Segoe UI", 7, "italic"), anchor="w")
        hint.grid(row=2, column=0, sticky="ew")

        conwrap = tk.Frame(right, bg=EDGE2, highlightthickness=1, highlightbackground=EDGE2)
        conwrap.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.console = tk.Text(conwrap, bg=PANEL, fg=TXT, wrap="none",
                               insertbackground=TURQ, selectbackground=BLUE,
                               font=("Consolas", 10), bd=0, padx=12, pady=8,
                               state="disabled", relief="flat", height=8)
        csb = ttk.Scrollbar(conwrap, command=self.console.yview)
        self.console.configure(yscrollcommand=csb.set)
        self.console.pack(fill="both", expand=True, side="left")
        csb.pack(fill="y", side="right")
        for tag, fg in (("time", DIM), ("ok", GREEN), ("err", RED), ("warn", AMBER),
                        ("sys", TURQ)):
            self.console.tag_configure(tag, foreground=fg)
        self.console.tag_configure("input", foreground=BLUE,
                                   font=("Consolas", 10, "bold"))

        talkm = tk.Frame(right, bg=BG)
        talkm.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        talk = tk.Frame(talkm, bg=PANEL)
        talk.pack(side="left", fill="x", expand=True)
        self.talk_lbl = tk.Label(talk, text=" TALK TO %s " % ENGINES[self.selected]["name"],
                                 bg=PANEL2, fg=TURQ, font=("Consolas", 9, "bold"),
                                 padx=6, pady=2)
        self.talk_lbl.pack(side="left", pady=4)
        self.talkvar = tk.StringVar()
        self.talkbox = tk.Entry(talk, textvariable=self.talkvar, bg=PANEL2, fg=TXT,
                                insertbackground=TURQ, relief="flat",
                                font=("Consolas", 11), highlightthickness=1,
                                highlightbackground=EDGE2, highlightcolor=TURQ)
        self.talkbox.pack(side="left", fill="x", expand=True, ipady=5, pady=4, padx=(6, 0))
        self.talkbox.bind("<Return>", lambda e: self.talk_send())
        self.talk_btn = tk.Label(talk, text=" SEND ", bg=blend(TURQ, BG, 0.82), fg=BG,
                                 font=("Consolas", 11, "bold"), padx=14, pady=5,
                                 cursor="hand2")
        self.talk_btn.pack(side="left", padx=(6, 0), pady=4)
        self.talk_btn.bind("<Button-1>", lambda e: self.talk_send())
        bottm = tk.Frame(self, bg=PANEL)
        bottm.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14,
                   pady=(6, 10))
        meters = tk.Frame(bottm, bg=PANEL)
        meters.pack(side="right", padx=(8, 0))
        self.g_cpu = Gauge(meters, "HOST CPU", TURQ)
        self.g_cpu.pack(side="left")
        self.g_ram = Gauge(meters, "HOST RAM", BLUE)
        self.g_ram.pack(side="left")
        self.g_out = Gauge(meters, "OUT RATE", GREEN,
                           fmtfn=lambda v: fmt_bytes(v) + "/s")
        self.g_out.pack(side="left")
        self.g_jobs = Gauge(meters, "ACTIVE", AMBER, fmt="%d")
        self.g_jobs.pack(side="left")
        self.chart = Sparkline(meters, TURQ)
        self.chart.pack(side="left", fill="both", expand=True)

        self.statusbar = tk.Label(bottm, text="", bg=PANEL, fg=DIM, anchor="w",
                                  font=("Segoe UI", 8), padx=12, pady=4)
        self.statusbar.pack(side="left", fill="both", expand=True)

    def _style_combos(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TXT, arrowcolor=TURQ, bordercolor=EDGE2,
                        lightcolor=EDGE2, darkcolor=EDGE2, selectbackground=BLUE,
                        selectforeground=BG, insertcolor=TXT)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", TXT)
        self.option_add("*TCombobox*Listbox.selectBackground", BLUE)
        self.option_add("*TCombobox*Listbox.selectForeground", BG)
        style.configure("Deck.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TXT, rowheight=26, borderwidth=0)
        style.configure("Deck.Treeview.Heading", background=PANEL2, foreground=DIM,
                        relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Deck.Treeview",
                  background=[("selected", blend(TURQ, BG, 0.7))],
                  foreground=[("selected", BG)])
        for orient in ("Vertical", "Horizontal"):
            style.configure(orient + ".TScrollbar",
                            background=blend(DIM, PANEL2, 0.5),
                            troughcolor=PANEL, bordercolor=EDGE2,
                            arrowcolor=DIM, lightcolor=EDGE2,
                            darkcolor=EDGE2)
            style.map(orient + ".TScrollbar",
                      background=[("active", blend(DIM, PANEL2, 0.85)),
                                  ("pressed", TURQ)])

    # ------------------------------------------------------------ console
    def console_append(self, engine_key, text, tag=None):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if tag is None and engine_key:
            low = text.lower()
            if re.search(r"\b(error|fatal|failed|failure)\b", low):
                tag = "err"
            elif re.search(r"\b(warning|denied|refused)\b", low):
                tag = "warn"
        prefix = "[%s] %-10s" % (now, ENGINES.get(engine_key, {}).get(
            "name", (engine_key or "").upper())) if engine_key else "[%s] " % now
        self.console.configure(state="normal")
        self.console.insert("end", prefix, "time")
        self.console.insert("end", text, tag if tag else ())
        self.console.configure(state="disabled")
        try:
            if self.console.yview()[1] > 0.98:
                self.console.see("end")
        except Exception:
            pass
        try:
            self.session_log.write(prefix.replace(" " * 40, " ") + text)
            self.session_log.flush()
        except Exception:
            pass

    def sysmsg(self, text):
        self.console_append(None, text + "\n", tag="sys")

    # ------------------------------------------------------------------ io
    def _drain(self):
        if not self._alive:
            return
        try:
            for _ in range(200):
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "out":
                    _, key, raw = item
                    raw = ANSI_RE.sub("", raw.replace("\r\n", "\n").replace("\r", "\n"))
                    self.out_bytes += len(raw.encode("utf-8", "ignore"))
                    disp = "\n".join(
                        ln for ln in raw.split("\n")
                        if not any(j in ln for j in DISPLAY_JUNK)
                        and not ln.lstrip().startswith("stty:"))
                    if disp.strip("\n"):
                        self.console_append(key, disp)
                        self._feed_findings(key, disp)
                elif kind == "exit":
                    _, key, rc = item
                    job = self.jobs.pop(key, None)
                    if job is not None:
                        file_flush(key, job.state,
                                   lambda e, a, b, c, **kw: self.add_finding(e, a, b, c, **kw))
                    tab = self.tabs.get(key)
                    if tab is not None:
                        if job is not None and job.stopped:
                            tab.status_kind = "stopped"
                        elif rc == 0:
                            tab.status_kind = "done"
                        else:
                            tab.status_kind = "fail"
                            tab.rc = rc
                    nm = ENGINES.get(key, {}).get("name", key.upper())
                    self.sysmsg("%s finished (exit %s)" % (nm, rc))
                elif kind == "probe":
                    self.probe_running = False
                    self._apply_probe(item[1])
                elif kind == "msg":
                    self.sysmsg(item[1])
        except queue.Empty:
            pass
        self.after(80, self._drain)

    def _feed_findings(self, key, text):
        state = None
        for j in self.jobs.values():
            if j.key == key:
                state = j.state
        if state is None:
            return
        def emit(eng, find, val, det, **kw):
            self.add_finding(eng, find, val, det, **kw)
        for ln in text.split("\n"):
            parse_line(key, ln, state, emit)

    # ------------------------------------------------------------ findings
    def add_finding(self, eng, find, val, det, **attrs):
        if not val and not find:
            return
        self.find_rows_seq += 1
        iid = "f%d" % self.find_rows_seq
        row = {"iid": iid, "eng": eng, "find": (find or "")[:300],
               "val": (val or "")[:4000], "det": (det or "")[:2000]}
        row.update(attrs)
        self.find_rows[iid] = row
        self.find_counts[eng] = self.find_counts.get(eng, 0) + 1
        t = self.tabs.get(eng)
        if t is not None:
            t.count = self.find_counts[eng]
        self._insert_row(row)
        self._update_deck_chip()
        self._update_ledger()

    def _insert_row(self, row):
        if self.deck_filter not in ("all", row["eng"]):
            return
        if not self._search_ok(row):
            return
        t = ENGINES[row["eng"]]
        tag = t["glyph"]
        self.deck.insert("", "end", iid=row["iid"], tags=(tag,),
                         values=(tag, row["find"], row["val"][:600],
                                 row["det"][:160]))

    def _search_ok(self, row):
        if not self.deck_search:
            return True
        hay = "%s %s %s" % (row["find"], row["val"], row["det"])
        return self.deck_search.lower() in hay.lower()

    def _render_deck(self):
        self.deck.delete(*self.deck.get_children())
        for row in self.find_rows.values():
            self._insert_row(row)
        self._update_deck_chip()

    def _update_deck_chip(self):
        shown = len(self.deck.get_children())
        total = len(self.find_rows)
        self.deck_chip.configure(
            text="%d shown / %d total" % (shown, total))

    def _update_ledger(self):
        parts = ["%s %d" % (ENGINES[k]["glyph"], self.find_counts[k])
                 for k in ENGINE_ORDER]
        self.ledger.configure(text="findings:  " + "   ".join(parts))

    def _sel_row(self):
        sel = self.deck.selection()
        if not sel or sel[0] not in self.find_rows:
            return None
        return self.find_rows[sel[0]]

    def _deck_wheel(self, event):
        d = event.delta
        if not d:
            return
        if event.state & 0x0001:
            self.deck.xview_scroll(int(1.3 * d / 120) * -16, "units")
        else:
            self.deck.yview_scroll(int(-2.0 * d / 120), "units")
        return "break"

    def _on_deck_release(self, event):
        try:
            if self.deck.identify_row(event.y) in ("", None) and \
                    self.deck.identify("region", event.x, event.y) != "cell":
                return
        except Exception:
            pass
        row = self._sel_row()
        if row is not None and \
                time.time() - getattr(self, "_last_popup_ts", 0.0) >= 0.40:
            self.after(10, lambda: self.deck_action(row, default=False))

    def set_deck_filter(self, val):
        self.deck_filter = val
        for v, chip in self.filter_chips.items():
            chip.configure(fg=(BG if v == val else DIM),
                           bg=(blend(TURQ, BG, 0.78) if v == val else PANEL2))
        self._render_deck()

    def set_deck_search(self):
        self.deck_search = self.searchvar.get().strip()
        self._render_deck()

    def clear_deck(self, confirm=False):
        if confirm and self.find_rows and \
                not messagebox.askyesno(APP_NAME,
                                        "wipe all %d findings from the deck?" %
                                        len(self.find_rows)):
            return
        self.find_rows.clear()
        self.find_counts = {k: 0 for k in ENGINE_ORDER}
        for t in self.tabs.values():
            t.count = 0
        self._render_deck()
        self._update_ledger()
        self._inspect_fill()
        self.sysmsg("findings deck cleared")

    def deck_action(self, row, default=False):
        if row is None:
            return
        self._last_popup_ts = time.time()
        menu = tk.Menu(self, tearoff=0, bg=PANEL2, fg=TXT,
                       activebackground=BLUE, activeforeground=BG,
                       font=("Segoe UI", 9))
        self._popup_menu = menu
        url = row.get("url")
        if url:
            menu.add_command(label=">> OPEN IN BROWSER", font=("Segoe UI", 9, "bold"),
                             foreground=TURQ,
                             command=lambda: self._open_url(url))
        menu.add_command(label="COPY VALUE", font=("Segoe UI", 9),
                         command=lambda: self._copy_row(row, "val"))
        menu.add_command(label="COPY FULL DETAIL", font=("Segoe UI", 9),
                         command=lambda: self._copy_detail(row))
        if row.get("detail2"):
            menu.add_command(label="SHOW FULL LINE", font=("Segoe UI", 9),
                             command=lambda: self._copy_row(row, "line"))
        if row.get("secret"):
            if row.get("revealed"):
                menu.add_command(label="RE-MASK SECRET", font=("Segoe UI", 9),
                                 foreground=AMBER,
                                 command=lambda: self._reveal_toggle(row, False))
            else:
                menu.add_command(label="REVEAL SECRET (careful)", font=("Segoe UI", 9, "bold"),
                                 foreground=RED,
                                 command=lambda: self._reveal_toggle(row, True))
            menu.add_command(label="COPY RAW SECRET", font=("Segoe UI", 9),
                             foreground=RED,
                             command=lambda: self._copy_raw_secret(row))
        menu.add_separator()
        pm = tk.Menu(menu, tearoff=0, bg=PANEL2, fg=TXT,
                     activebackground=BLUE, activeforeground=BG,
                     font=("Segoe UI", 9))
        for k in ENGINE_ORDER:
            pm.add_command(label="to %s" % ENGINES[k]["name"],
                           command=lambda kk=k: self._pivot(kk, row))
        menu.add_cascade(label="PIVOT VALUE ->", menu=pm)
        host = self._host_of(row)
        if host:
            lanes = tk.Menu(menu, tearoff=0, bg=PANEL2, fg=TXT,
                            activebackground=BLUE, activeforeground=BG,
                            font=("Segoe UI", 9))
            lanes.add_command(label="WHOIS registry",
                              command=lambda: self._quick_lane("whois", host))
            lanes.add_command(label="DIG dns records",
                              command=lambda: self._quick_lane("dig", host))
            menu.add_cascade(label="QUICK LANES ->", menu=lanes)
        menu.add_separator()
        menu.add_command(label="REMOVE ROW", font=("Segoe UI", 9),
                         command=lambda: self._remove_row(row))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()
        _ = default

    def _open_url(self, url):
        try:
            webbrowser.open(url)
            self.sysmsg("opened: %s" % url)
        except Exception as e:
            self.sysmsg("cannot open url: %s" % e)

    def _copy_row(self, row, field):
        self.clipboard_clear()
        self.clipboard_append(row.get(field, ""))
        self.sysmsg("copied to clipboard")

    def _copy_raw_secret(self, row):
        self.clipboard_clear()
        self.clipboard_append(row.get("secret", ""))
        self.sysmsg("raw secret copied - handle it with gloves on")

    @staticmethod
    def _finding_text(row):
        eng = ENGINES.get(row["eng"], {}).get("name", row["eng"])
        lines = ["SCOUT: %s" % eng,
                 "FINDING: %s" % row.get("find", "")]
        if row.get("url"):
            lines.append("URL: %s" % row["url"])
        lines.append("VALUE: %s" % row.get("val", ""))
        lines.append("DETAIL: %s" % row.get("det", ""))
        for kk, vv in row.items():
            if kk in ("iid", "eng", "find", "val", "det", "url",
                      "secret", "revealed", "detail2", "line"):
                continue
            if vv in (None, ""):
                continue
            lines.append("%s: %s" % (kk.upper(), vv))
        return "\n".join(lines)

    def _inspect_fill(self):
        row = self._sel_row()
        if row is None or self._view_row is None or \
                row["iid"] != self._view_row["iid"]:
            self._view_rawline = False
        self._view_row = row
        t = self.viewer
        t.configure(state="normal")
        t.delete("1.0", "end")
        if row is None:
            t.insert("1.0", " double-click a finding -\n its full content opens here")
            self.view_chip.configure(text="double-click a finding -", fg=DIM)
        else:
            t.insert("1.0", self._finding_text(row))
            if self._view_rawline and row.get("detail2"):
                t.insert("end", "\n\n----- RAW LINE -----\n" + row["detail2"])
            self.view_chip.configure(text="panel armed - actions live", fg=TURQ)
        t.see("1.0")
        t.configure(state="disabled")

    def _viewer_open(self):
        row = self._sel_row()
        if row is None:
            self.sysmsg("nothing selected - double-click a finding on the deck")
            return
        self._view_row = None
        self._view_rawline = False
        m = getattr(self, "_popup_menu", None)
        if m is not None:
            try:
                m.unpost()
            except Exception:
                pass
            self._popup_menu = None
        self._inspect_fill()
        self.sysmsg("finding opened on the FINDING CONTENT panel")

    def _view_msg(self):
        row = self._view_row
        if row is None:
            self.sysmsg("panel is empty - double-click a finding first")
        return row

    def _view_open(self):
        row = self._view_msg()
        if row is None:
            return
        if row.get("url"):
            self._open_url(row["url"])
        else:
            self.sysmsg("no url on this finding - nothing to open")

    def _view_reveal(self):
        row = self._view_msg()
        if row is None:
            return
        if not row.get("secret"):
            self.sysmsg("nothing masked on this finding")
            return
        self._reveal_toggle(row, not row.get("revealed"))

    def _view_raw(self):
        row = self._view_msg()
        if row is None:
            return
        if not row.get("detail2"):
            self.sysmsg("no raw line stored on this finding")
            return
        self._view_rawline = not self._view_rawline
        self._inspect_fill()
        self.sysmsg("raw line %s on the panel"
                    % ("shown" if self._view_rawline else "hidden"))

    def _view_pivot(self):
        row = self._view_msg()
        if row is None:
            return
        self.deck_action(row, default=False)

    def _view_copy_val(self):
        row = self._view_msg()
        if row is None:
            return
        self._copy_row(row, "val")

    def _view_copy_full(self):
        row = self._view_msg()
        if row is None:
            return
        self._copy_detail(row)

    def _view_lane(self, lane):
        row = self._view_msg()
        if row is None:
            return
        host = self._host_of(row)
        if not host:
            self.sysmsg("no host/domain inside this finding for %s"
                        % lane.upper())
            return
        self._quick_lane(lane, host)

    def _toggle_full(self):
        try:
            if self.wm_state() == "zoomed":
                self.wm_state("normal")
                self.geometry("1400x860")
                self.full_btn.configure(text=" FULL SCREEN ")
                self.sysmsg("window restored - FULL SCREEN grows it back")
            else:
                self.wm_state("zoomed")
                self.full_btn.configure(text=" RESTORE ")
                self.sysmsg("full screen on - RESTORE gives the window back")
        except Exception as e:
            self.sysmsg("window size toggle failed: %s" % e)

    def _copy_detail(self, row):
        self.clipboard_clear()
        self.clipboard_append(self._finding_text(row))
        self.sysmsg("full finding detail copied")

    @staticmethod
    def _host_of(row):
        url = row.get("url")
        if url:
            try:
                return URL_RE.match(url).group(0).split("/")[2].lower()
            except Exception:
                pass
        v = (row.get("val", "") or "").strip()
        if re.match(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$", v,
                    re.I):
            return v.lower()
        return None

    def _quick_lane(self, lane, host):
        if self.jobs.get(lane):
            self.sysmsg("%s quick lane is already running - let it finish"
                        % lane.upper())
            return
        if lane == "whois":
            cmdline = 'whois "%s"' % host
        else:
            cmdline = 'dig "%s" +noall +answer +nomultiline' % host
        job = Job(lane, cmdline, self)
        self.jobs[lane] = job
        job.start()
        self.sysmsg("QUICK LANE %s:  %s" % (lane.upper(), cmdline))

    @staticmethod
    def _is_path(val):
        if val.startswith("/"):
            return True
        if not re.match(r"^[A-Za-z]:[\\/]", val):
            return False
        try:
            return os.path.exists(val)
        except Exception:
            return True

    def _reveal_toggle(self, row, show):
        row["revealed"] = show
        det = row.get("secret", "") if show else mask_secret(row.get("secret", ""))
        row["det"] = det[:160]
        self.deck.set(row["iid"],
                      values=(ENGINES[row["eng"]]["glyph"], row["find"],
                              row["val"], row["det"]))
        self._inspect_fill()

    def _remove_row(self, row):
        eng = row["eng"]
        if self.find_counts.get(eng):
            self.find_counts[eng] -= 1
        t = self.tabs.get(eng)
        if t is not None and t.count >= 0:
            t.count = self.find_counts[eng]
        self.find_rows.pop(row["iid"], None)
        self.deck.delete(row["iid"])
        self._inspect_fill()
        self._update_deck_chip()
        self._update_ledger()

    def _pivot(self, eng_key, row):
        val = row.get("val", "")
        if not val:
            return
        self.select_engine(eng_key)
        ph = ENGINES[eng_key]["ph"]
        cur = self.cmdvar.get()
        if re.search(r"<[^>]+>", cur):
            self.cmdvar.set(re.sub(r"<[^>]+>", val, cur, count=1))
        else:
            self.cmdvar.set('%s "[%s]"' % (cur.split(" ")[0], val))
        self.sysmsg("pivoted into %s: %s" % (ENGINES[eng_key]["name"], val))

    def export_deck(self):
        rows = list(self.find_rows.values())
        if not rows:
            self.sysmsg("nothing to export yet - hunt something first")
            return
        p = filedialog.asksaveasfilename(
            title="export findings", defaultextension=".csv",
            initialfile="XXxVector_SourcingxXX-findings.csv",
            filetypes=(("CSV", "*.csv"), ("TXT", "*.txt"), ("All files", "*.*")))
        if not p:
            return
        try:
            if p.lower().endswith(".txt"):
                with open(p, "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write("%s\t%s\t%s\t%s\n" % (r["eng"], r["find"],
                                                      r["val"], r["det"]))
            else:
                import csv
                with open(p, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["scout", "finding", "value", "detail"])
                    for r in rows:
                        w.writerow([r["eng"], r["find"], r["val"], r["det"]])
            self.sysmsg("exported %d findings -> %s" % (len(rows), p))
        except Exception as e:
            self.sysmsg("export failed: %s" % e)

    # ------------------------------------------------------------ sensors
    def _tick_sensors(self):
        if not self._alive:
            return
        if psutil:
            self.g_cpu.set(psutil.cpu_percent(None))
            self.g_ram.set(psutil.virtual_memory().percent)
        self.after(900, self._tick_sensors)

    def _tick_ui(self):
        if not self._alive:
            return
        per_tick = self.out_bytes - self._last_bytes
        self._last_bytes = self.out_bytes
        per_sec = per_tick / 0.06
        self.g_out.set(min(100.0, per_sec / 2048.0))
        self.g_out.set_raw(per_sec)
        self.g_jobs.set(len(self.jobs))
        for g in (self.g_cpu, self.g_ram, self.g_out, self.g_jobs):
            g.tick()
        self.chart.tick(per_sec)
        for t in self.tabs.values():
            t.paint()
        for key, job in self.jobs.items():
            el = int(time.time() - job.t0)
            self.tabs[key].elapsed = "%02d:%02d" % (el // 60, el % 60)
        if self.jobs:
            self.live_chip.configure(text="HUNTING x%d" % len(self.jobs),
                                     bg=blend(TURQ, BG, 0.8), fg=BG)
        else:
            self.live_chip.configure(text="STANDBY", bg=PANEL2, fg=DIM)
        self.refresh_stages()
        self.stop_btn.configure(fg=RED if self.jobs.get(self.selected) else DIM)
        self.statusbar.configure(
            text="%s %s  -  %s & %s   |   distro: %s   |   findings: %d   |   lines: %d"
                 "   |   out: %s   |   logs: %s" % (
                APP_NAME, APP_VER, CREATORS[0], CREATORS[1], DISTRO,
                len(self.find_rows), self.lines_out, fmt_bytes(self.out_bytes),
                self.logs_dir))
        self.after(60, self._tick_ui)

    # ------------------------------------------------------------ actions
    def select_engine(self, key):
        if key not in ENGINES:
            self.sysmsg("scout not in this rack: %s" % key)
            return
        self.selected = key
        self.toolvar.set(ENGINES[key]["name"])
        self.talk_lbl.configure(text=" TALK TO %s " % ENGINES[key]["name"])
        self.cmdbox["values"] = tuple(ENGINES[key].get("presets") or
                                      (ENGINES[key]["preset"],))
        if not self.jobs.get(key):
            self.cmdvar.set(ENGINES[key]["preset"])
        self._on_target()

    def _on_toolbox(self):
        name = self.toolvar.get()
        for k, t in ENGINES.items():
            if t["name"] == name:
                self.select_engine(k)
                return

    def run_selected(self):
        key = self.selected
        if self.jobs.get(key):
            self.sysmsg("%s is already running - STOP it first" % ENGINES[key]["name"])
            return
        cmdline = self.cmdvar.get().strip()
        if not cmdline:
            self.sysmsg("command is empty")
            return
        if re.search(r"<[^>]+>", cmdline):
            val = self.targetvar.get().strip() if getattr(self, "targetvar", None) else ""
            if not val:
                self.sysmsg("unfilled <placeholder> - type the %s in the TARGET box (or BROWSE a file)"
                            % ENGINES[key]["pivot_hint"])
                return
            ph = ENGINES[key]["ph"]
            if ph in ("<file>", "<target-dir>") and not self._is_path(val):
                self.sysmsg("%s scans FILES/FOLDERS - use BROWSE; '%s' does not "
                            "look like a path" % (ENGINES[key]["name"], val))
                return
            if ph == "<domain>" and "." not in val:
                self.sysmsg("%s wants a DOMAIN like site.com - '%s' has no dot "
                            "(names go to Sherlock)" % (ENGINES[key]["name"], val))
                return
            cmdline = re.sub(r"<[^>]+>", val, cmdline, count=1)
            self.cmdvar.set(cmdline)
            self.sysmsg("TARGET box filled in: %s" % val)
        job = Job(key, cmdline, self)
        self.jobs[key] = job
        t = self.tabs[key]
        t.status_kind = "run"
        t.rc = None
        t.elapsed = "00:00"
        job.start()
        self.sysmsg("LAUNCHED %s:  %s" % (ENGINES[key]["name"], cmdline))

    def stop_selected(self):
        job = self.jobs.get(self.selected)
        if not job:
            return
        job.stop()
        self.sysmsg("STOP sent to %s" % ENGINES[self.selected]["name"])

    def _on_target(self, *args):
        if not getattr(self, "targetvar", None):
            return
        val = self.targetvar.get().strip()
        cur = self.cmdvar.get()
        if not val:
            if re.search(r"<[^>]+>", cur):
                self.cmdvar.set(ENGINES[self.selected]["preset"])
            return
        if re.search(r"<[^>]+>", cur):
            self.cmdvar.set(re.sub(r"<[^>]+>", val, cur, count=1))
        else:
            toks = cur.split(" ")
            if len(toks) > 1 and toks[1].startswith('"') and toks[1].endswith('"'):
                toks[1] = '"%s"' % val
                self.cmdvar.set(" ".join(toks))

    def talk_send(self):
        key = self.selected
        line = self.talkvar.get().strip()
        if not line:
            return
        job = self.jobs.get(key)
        if job is None:
            self.sysmsg("%s is not running - RUN it first, then type to it here"
                        % ENGINES[key]["name"])
            return
        if job.send(line):
            self.console_append(key, ">>> %s\n" % line, tag="input")
            self.talkvar.set("")
        else:
            self.sysmsg("cannot send - %s window is closing" % ENGINES[key]["name"])

    def open_wsl_console(self):
        try:
            subprocess.Popen([WSL_EXE, "-d", DISTRO],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            self.sysmsg("cannot open wsl console: %s" % e)

    def browse_target(self):
        p = filedialog.askopenfilename(
            title="pick a file (image / pdf / doc / or any file inside a repo)")
        if not p:
            return
        wp = to_wsl_path(p)
        key = self.selected
        cur = self.cmdvar.get()
        if key == "leaks":
            wp = to_wsl_path(os.path.dirname(p))
            self.sysmsg("scanning the whole folder holding that file: %s" % wp)
        if re.search(r"<[^>]+>", cur):
            self.cmdvar.set(re.sub(r"<[^>]+>", wp, cur, count=1))
        else:
            self.cmdvar.set(cur + ' "' + wp + '"')
        self.sysmsg("target loaded: %s" % wp)

    def refresh_stages(self):
        for k, lamp in self.stage_lamps.items():
            job = self.jobs.get(k)
            t = self.tabs[k]
            if job is not None and t.status_kind == "run":
                lamp.configure(bg=BLUE, fg=PANEL)
            elif job is not None and t.status_kind == "done" and (t.rc or 0) == 0:
                lamp.configure(bg=TURQ, fg=PANEL)
            elif t.status_kind in ("done",) and (t.rc or 0) == 0:
                lamp.configure(bg=blend(TURQ, PANEL2, 0.35), fg=TXT)
            elif t.status_kind in ("fail", "missing"):
                lamp.configure(bg=blend(RED, PANEL2, 0.55), fg=TXT)
            else:
                lamp.configure(bg=PANEL2, fg=DIM)

    # ------------------------------------------------------------ engines
    def probe_engines(self):
        if self.probe_running:
            return
        self.probe_running = True
        for t in self.tabs.values():
            if t.status_kind == "idle":
                t.status_kind = "probe"
        self.sysmsg("checking scouts inside %s ..." % DISTRO)

        def work():
            rc, out = run_wsl_b64(PROBE_SCRIPT, 180)
            results = {}
            for line in out.splitlines():
                if "|" in line:
                    name, ver = line.split("|", 1)
                    results[name.strip()] = ver.strip()
            if not results:
                results = {"_err": out[-300:] or ("rc=%d" % rc)}
            self.put(("probe", results))
        threading.Thread(target=work, daemon=True).start()

    def _apply_probe(self, results):
        self.sysmsg("scout check: %s" % json.dumps(results))
        lane = {"sherlock": "sherlock", "harv": "theHarvester", "amass": "amass",
                "exif": "exiftool", "leaks": "gitleaks"}
        for k in ENGINE_ORDER:
            ver = results.get(lane[k])
            t = self.tabs[k]
            if ver is None:
                t.status_kind = "idle"
                continue
            if "MISSING" in ver:
                t.status_kind = "missing"
            else:
                t.status_kind = "detect"
                t.ver = ver
        if any(t.status_kind == "missing" for t in self.tabs.values()):
            self.sysmsg("one or more scouts missing - hit PULL MISSING SCOUTS")

    def install_engines(self):
        slot = ENGINE_ORDER[0]
        if self.jobs.get(slot):
            self.sysmsg("%s slot busy - STOP it first for a reinstall"
                        % ENGINES[slot]["name"])
            return
        self.sysmsg("PULL: apt-get install %s (watch the stream)" % INSTALL_PKGS)
        script = ("export DEBIAN_FRONTEND=noninteractive; "
                  "apt-get update -y; "
                  "apt-get install -y --no-install-recommends %s; "
                  "echo INSTALL_DONE_RC=$?" % INSTALL_PKGS)
        job = Job(slot, script, self)
        self.jobs[slot] = job
        t = self.tabs[slot]
        t.status_kind = "run"
        t.rc = None
        t.elapsed = "00:00"
        job.start()


def main():
    app = App()
    try:
        p = res_path("icon.png")
        if os.path.exists(p):
            img = tk.PhotoImage(file=p)
            app._icon_img = img
            app.tk.call("wm", "iconphoto", app._w, img)
    except Exception:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
