"""HexJacked - the mobile & binary workbench for five engines (WSL Kali underneath)."""
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
import webbrowser

APP_NAME = "HexJacked"
APP_VER = "1.1.0"
CREATORS = ("XxREPTILExX", "XxNEOPAULxX")
DISTRO = "kali-linux"

BG = "#0A0F16"
PANEL = "#0F1723"
PANEL2 = "#131E2C"
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

TOOLS = {
    "jadx": {
        "bin": "jadx", "name": "JADX - Decompile", "sub": "APK/DEX -> Java source",
        "glyph": "JDX", "color": TURQ,
        "preset": 'jadx -d /tmp/hexjacked-out "<file>"',
        "presets": (
            'jadx -d /tmp/hexjacked-out "<file>"',
            'jadx -d /tmp/hexjacked-out --show-bad-code -s "<file>"',
            'apktool d -f "<file>"',
        ),
    },
    "mobsf": {
        "bin": "Mobile-Security-Framework",
        "name": "MobSF - Static Scan", "sub": "Mobile pen-test framework",
        "glyph": "MBF", "color": BLUE,
        "preset": "cd /opt/mobsf/Mobile-Security-Framework-MobSF"
                  " && /root/.cache/pypoetry/virtualenvs/mobsf-MxG4Buoj-py3.13"
                  "/bin/python manage.py runserver 0.0.0.0:8000",
        "presets": (
            "cd /opt/mobsf/Mobile-Security-Framework-MobSF"
            " && /root/.cache/pypoetry/virtualenvs/mobsf-MxG4Buoj-py3.13"
            "/bin/python manage.py runserver 0.0.0.0:8000",
            'mobsfscan "<file-or-dir>"',
            'mobsfscan --json "<file-or-dir>"',
        ),
    },
    "frida": {
        "bin": "frida", "name": "Frida - Live Hooks",
        "sub": "Dynamic instrumentation",
        "glyph": "FRD", "color": TURQ,
        "preset": "frida-ps -U",
        "pty": True,
        "presets": (
            "frida-ps -U",
            "frida-ps -Ua",
            'frida-trace -U -f "<package>"',
            'frida -U -f "<package>" -l "<script.js>"',
        ),
    },
    "impacket": {
        "bin": "impacket-", "name": "Impacket - Network",
        "sub": "AD / SMB / lateral movement",
        "glyph": "IMP", "color": BLUE,
        "preset": 'impacket-smbclient "<host>"',
        "pty": True,
        "presets": (
            'impacket-smbclient "<host>"',
            'impacket-secretsdump "<dom>/<user>:<pass>@<host>"',
            'impacket-psexec "<dom>/<user>:<pass>@<host>"',
            'impacket-getuserspns "<dom>/<user>:<pass>" -request',
        ),
    },
    "hashcat": {
        "bin": "hashcat", "name": "Hashcat - Crack",
        "sub": "Password recovery (CPU OpenCL)",
        "glyph": "HSH", "color": TURQ,
        "preset": "hashcat -b -m 0",
        "presets": (
            "hashcat -b -m 0",
            'hashcat -m 0 "<hashes.txt>" /usr/share/wordlists/rockyou.txt',
            'hashcat -m 1000 "<hashes.txt>" /usr/share/wordlists/rockyou.txt',
            'hashcat -m 22000 "<hc22000.txt>" /usr/share/wordlists/rockyou.txt',
        ),
    },
}
TOOL_ORDER = ["jadx", "mobsf", "frida", "impacket", "hashcat"]

INSTALL_PKGS = ("jadx apktool hashcat python3-impacket pocl-opencl-icd "
                "ocl-icd-libopencl1 python3-pip")

PROBE_SCRIPT = (
    "for b in jadx mobsfscan frida hashcat impacket-smbclient; do "
    "if command -v \"$b\" >/dev/null 2>&1; then "
    "v=$(\"$b\" --version 2>/dev/null | head -n1); "
    "[ -z \"$v\" ] && v=$(\"$b\" -V 2>/dev/null | head -n1); "
    "[ -z \"$v\" ] && v=detected; "
    "echo \"$b|$v\"; else echo \"$b|MISSING\"; fi; done; "
    "if [ -d /opt/mobsf/Mobile-Security-Framework-MobSF/.git ]; then "
    "echo mobsf-server|MobSF-installed; else echo mobsf-server|MISSING; fi"
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


class Job:
    def __init__(self, key, cmdline, ctx):
        self.key = key
        self.cmdline = cmdline
        self.ctx = ctx
        self.t0 = time.time()
        self.proc = None
        self.stopped = False
        self.rc = None
        self.log = open(os.path.join(ctx.logs_dir, "%s-%s.log" % (
            key, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))), "a", encoding="utf-8")
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        cmdline = self.cmdline
        if TOOLS.get(self.key, {}).get("pty"):
            cmdline = "script -qec %s /dev/null" % shq(self.cmdline)
        cmd = [WSL_EXE, "-d", DISTRO, "-u", "root", "--", "bash", "-lc", cmdline]
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
        binname = TOOLS[self.key]["bin"]
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
        super().__init__(parent, width=112, height=172, bg=PANEL, highlightthickness=0)
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
        w, h = 112, 172
        frac = max(0.0, min(1.0, self.display / 100.0 if self.fmt == "%.0f%%" else
                            min(1.0, self.display / max(1.0, self.tgt * 1.25))))
        bx, bw = 30, 30
        bt, bb = 34, h - 36
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
        c.create_text(w // 2, 16, text=self.label, fill=DIM, font=("Segoe UI", 9, "bold"))
        val = self.fmtfn(self.raw) if self.fmtfn else self.fmt % self.display
        c.create_text(w // 2, h - 15, text=val, fill=TXT, font=("Consolas", 12, "bold"))


class Sparkline(tk.Canvas):
    def __init__(self, parent, color):
        super().__init__(parent, width=560, height=172, bg=PANEL, highlightthickness=0)
        self.color = color
        self.data = [0.0] * 140
        self.peak = 1.0

    def tick(self, v):
        self.data.append(max(0.0, float(v)))
        self.data = self.data[-140:]
        mx = max(self.data)
        if mx > self.peak or mx < self.peak * 0.05:
            self.peak = max(1.0, mx)
        self.onpaint()

    def onpaint(self):
        c = self
        c.delete("all")
        w = max(300, int(c.winfo_width()) or 560)
        h = 172
        top, bottom = 30, h - 24
        for i in range(1, 5):
            y = top + (bottom - top) * i / 4.0
            c.create_line(46, y, w - 14, y, fill=EDGE, dash=(2, 4))
        step = (w - 60) / float(len(self.data) - 1 or 1)
        poly = []
        for i, v in enumerate(self.data):
            x = 46 + i * step
            y = bottom - (bottom - top) * (v / self.peak)
            poly.append((x, y))
        if len(poly) > 1:
            c.create_polygon([(46, bottom)] + poly + [(poly[-1][0], bottom)],
                             fill=blend(self.color, BG, 0.16), outline="")
            c.create_line(poly, fill=self.color, width=2, smooth=True)
        c.create_text(w // 2, 12, text="ENGINE OUTPUT RATE", fill=DIM, font=("Segoe UI", 9, "bold"))
        c.create_text(w - 70, top, text="peak %s/s" % fmt_bytes(self.peak), fill=DIM,
                      font=("Consolas", 8))


class Tile(tk.Frame):
    def __init__(self, parent, ctx, key):
        super().__init__(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=EDGE, cursor="hand2")
        self.ctx = ctx
        self.key = key
        t = TOOLS[key]
        self.status_kind = "idle"
        self.ver = ""
        self.elapsed = ""
        self.rc = None
        self.phase = 0.0

        top = tk.Frame(self, bg=PANEL)
        top.pack(fill="x", padx=10, pady=(9, 2))
        cv = tk.Canvas(top, width=40, height=40, bg=PANEL, highlightthickness=0)
        cv.create_oval(2, 2, 38, 38, fill=t["color"])
        cv.create_text(20, 20, text=t["glyph"], fill=BG, font=("Consolas", 9, "bold"))
        cv.pack(side="left")
        rb = tk.Frame(top, bg=PANEL)
        rb.pack(side="left", fill="x", expand=True, padx=(10, 0))
        tk.Label(rb, text=t["name"], bg=PANEL, fg=TXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(rb, text=t["sub"], bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")
        self.chip = tk.Label(self, text="", bg=PANEL2, fg=DIM,
                             font=("Consolas", 8, "bold"), padx=8, pady=2, anchor="w")
        self.chip.pack(fill="x", padx=10, pady=(6, 8))
        self.bind("<Button-1>", self._click)
        for w in self.winfo_children():
            w.bind("<Button-1>", self._click)
        self._paint_chip()

    def _click(self, e):
        self.ctx.select_tool(self.key)

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
        t = TOOLS[self.key]
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
        parts = [t["bin"], txt, self.elapsed if self.status_kind == "run" else ""]
        if self.status_kind == "detect" and self.ver:
            parts = [t["bin"], self.ver[:34]]
        self.chip.configure(fg=col, text=" ".join(x for x in parts if x))


def sigbar(pct):
    n = max(1, min(5, int(round(pct / 20.0))))
    return "#" * n + "-" * (5 - n) + " %d%%" % (pct or 0)


SEV_RANK = {"CRITICAL": 4, "ERROR": 3, "HIGH": 3, "WARNING": 2, "MEDIUM": 2,
            "INFO": 1, "LOW": 1}

CHAIN_TEMPLATE = (
    "rm -rf /tmp/hexjacked-out; "
    "jadx -d /tmp/hexjacked-out \"<file>\" > /tmp/hex-jadx.log 2>&1; JX=$?; "
    "if [ -d /tmp/hexjacked-out/sources ]; then SRC=/tmp/hexjacked-out/sources; "
    "else SRC=/tmp/hexjacked-out; fi; "
    "mobsfscan --json \"$SRC\" > /tmp/hex-findings.json 2>>/tmp/hex-jadx.log; MB=$?; "
    "NJ=$(find /tmp/hexjacked-out -name '*.java' 2>/dev/null | wc -l); "
    "echo HEX_CHAIN jadx_rc=$JX mobsfscan_rc=$MB java_files=$NJ; exit 0"
)

FETCH_SCRIPT = (
    "J=/tmp/hex-findings.json; "
    "if [ -f \"$J\" ]; then "
    "echo NJAVA=$(find /tmp/hexjacked-out -name '*.java' 2>/dev/null | wc -l); "
    "echo JSONB64=$(base64 -w0 \"$J\"); "
    "else echo NO_JSON; fi"
)

FPRINT_SCRIPT = (
    "p=%s; "
    "echo SIZE=$(stat -c '%%s' \"$p\"); "
    "echo MD5=$(md5sum \"$p\" | cut -d' ' -f1); "
    "echo SHA256=$(sha256sum \"$p\" | cut -d' ' -f1); "
    "echo MIME=$(file -b --mime-type \"$p\")"
)


def wsl_unc(path):
    return "\\\\wsl.localhost\\" + DISTRO + path.replace("/", "\\")


def parse_mobsfscan_json(js):
    """mobsfscan --json (live format 1.2.0): results = {rule_id: {
    files: [{file_path, match_lines, match_position, match_string}],
    metadata: {severity, description, owasp-mobile, masvs, reference}}}.
    Policy rules carry metadata only. Returns flat finding dicts."""
    out = []
    try:
        d = json.loads(js)
    except Exception as e:
        return [{"rule": "PARSE-ERROR", "sev": "WARNING", "rank": 0,
                 "file": "", "ln": "", "match": "", "meta": {}, "files": 0,
                 "msg": "findings json unreadable: %s" % e,
                 "ref": ""}]
    n_err = len(d.get("errors") or [])
    rs = d.get("results")
    if not isinstance(rs, dict):
        rs = {}
    for rule in rs:
        v = rs[rule]
        if not isinstance(v, dict):
            continue
        md = v.get("metadata") or {}
        sev = (md.get("severity") or "INFO").upper()
        rank = SEV_RANK.get(sev, 1)
        desc = md.get("description") or ""
        files = v.get("files")
        if isinstance(files, list) and files:
            for f in files:
                ml = f.get("match_lines") or [0]
                out.append({"rule": rule, "sev": sev, "rank": rank,
                            "file": f.get("file_path") or "",
                            "ln": ml[0], "match": f.get("match_string") or "",
                            "meta": md, "files": 1, "msg": desc,
                            "ref": md.get("reference") or ""})
        else:
            out.append({"rule": rule, "sev": sev, "rank": rank,
                        "file": "", "ln": "", "match": "", "meta": md,
                        "files": 0, "msg": desc,
                        "ref": md.get("reference") or ""})
    if n_err:
        out.append({"rule": "SCAN-ERRORS", "sev": "WARNING", "rank": 0,
                    "file": "", "ln": "", "match": "", "meta": {},
                    "files": 0, "msg": "%d engine error(s) inside the scan"
                    % n_err, "ref": ""})
    out.sort(key=lambda r: (-r["rank"], r["rule"], r["file"]))
    return out


def finding_rowvals(f):
    fb = os.path.basename(f["file"]) if f["file"] else "(policy)"
    match = (f["match"] or f["msg"] or "").strip()
    match = " ".join(match.split())[:80]
    return (f["sev"], f["rule"], fb, str(f["ln"]), match)


def parse_wlan_scan(text):
    entries = []
    cur = None
    curb = None
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("Interface name"):
            cur = None
            curb = None
            continue
        if s.startswith("SSID ") and " : " in s:
            name = s.split(" : ", 1)[1].strip()
            cur = {"ssid": name if name else "(hidden)",
                   "auth": "", "cipher": "", "bssids": []}
            entries.append(cur)
            curb = None
            continue
        if cur is None:
            continue
        if ":" not in s:
            continue
        key, val = s.split(":", 1)
        key = key.strip()
        val = val.strip()
        if key.startswith("Authentication"):
            cur["auth"] = val
        elif key.startswith("Encryption"):
            cur["cipher"] = val
        elif key.startswith("BSSID"):
            curb = {"bssid": val.lower(), "sig": 0, "ch": "", "radio": "", "band": ""}
            cur["bssids"].append(curb)
        elif curb is not None:
            if key.startswith("Signal"):
                try:
                    curb["sig"] = int(val.rstrip("%"))
                except Exception:
                    pass
            elif key.startswith("Channel"):
                curb["ch"] = val
            elif key.startswith("Radio type"):
                curb["radio"] = val
            elif key.startswith("Band"):
                curb["band"] = val
    for e in entries:
        if e["bssids"]:
            e["maxsig"] = max(b["sig"] for b in e["bssids"])
            strong = max(e["bssids"], key=lambda b: b["sig"])
            e["strong"] = strong
            e["chs"] = "/".join(dict.fromkeys(b["ch"] for b in e["bssids"]))
            e["n"] = len(e["bssids"])
        else:
            e["maxsig"] = 0
            e["strong"] = None
            e["chs"] = "?"
            e["n"] = 0
    entries.sort(key=lambda e: -e["maxsig"])
    return entries


def get_lan_subnet():
    try:
        p = subprocess.run(["ipconfig"], capture_output=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        text = p.stdout.decode("utf-8", "replace")
    except Exception:
        return None
    ips = []
    for line in text.splitlines():
        if "IPv4" in line and ":" in line:
            val = line.split(":", 1)[1].strip().split("(")[0].strip()
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", val):
                ips.append(val)
    cands = [ip for ip in ips if ip.startswith("192.168.")]
    if not cands:
        cands = [ip for ip in ips if ip.startswith("10.")]
    if not cands:
        cands = [ip for ip in ips if not ip.startswith(("127.", "100.", "169.254."))]
    if not cands:
        return None
    return cands[0].rsplit(".", 1)[0] + ".0/24"


class NetworkPanel(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("%s - Network Selector" % APP_NAME)
        self.configure(bg=BG)
        self.geometry("700x560")
        self.minsize(620, 470)
        self.rows = {}
        self.seen = {}
        self.sel_iid = None

        head = tk.Frame(self, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text="NETWORK SELECTOR", bg=PANEL, fg=TURQ,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=(12, 8), pady=10)
        self.status = tk.Label(head, text="scanning...", bg=PANEL, fg=DIM,
                               font=("Consolas", 8))
        self.status.pack(side="left")
        self.rescan_btn = tk.Label(head, text=" RESCAN ", bg=PANEL2, fg=BLUE,
                                   font=("Consolas", 9, "bold"), padx=10, pady=4,
                                   cursor="hand2")
        self.rescan_btn.pack(side="right", padx=(0, 12))
        self.rescan_btn.bind("<Button-1>", lambda e: self.app.start_netscan())

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=12, pady=(8, 4))
        self.tree = ttk.Treeview(mid, columns=("ssid", "sig", "ch", "auth", "bssid"),
                                 show="headings", style="Net.Treeview")
        for cid, txt, w in (("ssid", "SSID", 210), ("sig", "SIGNAL", 110),
                            ("ch", "CH", 60), ("auth", "AUTH", 150),
                            ("bssid", "BSSID", 140)):
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor="w", stretch=(cid == "ssid"))
        vsb = ttk.Scrollbar(mid, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_sel)

        self.info = tk.Label(self, text="select a network row", bg=BG, fg=DIM,
                             font=("Segoe UI", 8), anchor="w", justify="left")
        self.info.pack(fill="x", padx=12, pady=(4, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=12, pady=(8, 12))
        for txt, fn, col in (
                ("USE AS TARGET", self._act_target, TURQ),
                ("ARM WIFITE", self._act_wifite, TURQ),
                ("AIM NMAP AT LAN", self._act_nmap, BLUE),
                ("COPY BSSID", self._act_copy, BLUE),
                ("CLOSE", self.destroy, DIM)):
            c = tk.Label(btns, text=" " + txt + " ", bg=PANEL2, fg=col,
                         font=("Consolas", 9, "bold"), padx=10, pady=6, cursor="hand2")
            c.pack(side="left", padx=(0, 8))
            c.bind("<Button-1>", lambda e, f=fn: f())

        self.bind("<Escape>", lambda e: self.destroy())
        self.after(6000, self._auto_loop)

    def _auto_loop(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self.app._alive and not self.app._scanning:
            self.app.start_netscan(silent=True)
        self.after(6000, self._auto_loop)

    KEEP_SECS = 120.0

    def _apply(self, entries, stamp):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        now = time.time()
        for e in entries:
            for b in e.get("bssids") or []:
                self.seen[(e["ssid"], b["bssid"])] = dict(e, b=b, last=now)
        for dead in [k for k, v in self.seen.items()
                     if now - v["last"] > self.KEEP_SECS]:
            self.seen.pop(dead, None)
        groups = {}
        for k, v in self.seen.items():
            groups.setdefault(k[0], []).append(v)
        merged = []
        for ssid, items in groups.items():
            newest = max(it["last"] for it in items)
            best = max(items, key=lambda it: it["b"]["sig"])
            merged.append({
                "ssid": ssid,
                "auth": items[0].get("auth", ""),
                "cipher": items[0].get("cipher", ""),
                "bssids": [it["b"] for it in items],
                "n": len(items),
                "chs": "/".join(dict.fromkeys(it["b"]["ch"] for it in items)),
                "maxsig": best["b"]["sig"],
                "strong": best["b"],
                "age": now - newest,
                "fresh": abs(newest - now) < 0.5,
            })
        merged.sort(key=lambda e: -e["maxsig"])
        prev = self.sel_iid
        self.rows = {}
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(merged):
            iid = str(i)
            self.rows[iid] = e
            strong = e.get("strong")
            b = strong["bssid"] if strong else "-"
            age = "now" if e["fresh"] else "%ds" % min(9999, int(e["age"]))
            vals = (e["ssid"][:38],
                    "%s %s" % (sigbar(e["maxsig"]), age),
                    e["chs"][:8], (e["auth"] or "?")[:20], b)
            self.tree.insert("", "end", iid=iid, values=vals)
        self.status.configure(text="%d networks   scanned %s   rows keep 120s" % (
            len(merged), stamp))
        if prev in self.rows:
            self.tree.selection_set(prev)
        else:
            self.sel_iid = None
            self.info.configure(text="select a network row")

    def _sel_entry(self):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.rows:
            return None
        return self.rows[sel[0]]

    def _on_sel(self, _e):
        e = self._sel_entry()
        if not e:
            return
        self.sel_iid = self.tree.selection()[0]
        strong = e.get("strong") or {}
        parts = ["%s   %s   ch %s   %s APs" % (e["ssid"], e["auth"] or "?",
                                               e["chs"], e["n"])]
        if strong:
            parts.append("strongest %s (%d%%, %s)" % (strong["bssid"],
                                                      strong["sig"], strong["radio"]))
        if e["cipher"]:
            parts.append("cipher %s" % e["cipher"])
        self.info.configure(text="    ".join(parts))

    def _act_target(self):
        e = self._sel_entry()
        if not e:
            self.app.sysmsg("pick a network row first")
            return
        self.app.use_as_target(e["ssid"])

    def _act_wifite(self):
        e = self._sel_entry()
        if not e:
            self.app.sysmsg("pick a network row first")
            return
        self.app.arm_wifite(e["ssid"])

    def _act_nmap(self):
        self.app.aim_nmap()

    def _act_copy(self):
        e = self._sel_entry()
        if not e:
            self.app.sysmsg("pick a network row first")
            return
        strong = e.get("strong")
        if not strong:
            self.app.sysmsg("no BSSID on that row")
            return
        self.app.copy_bssid(strong["bssid"])


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
        self.netpanel = None
        self._scanning = False
        self.selected = TOOL_ORDER[0]
        self.out_bytes = 0
        self.lines_out = 0
        self._last_bytes = 0
        self._probe_seen = 0
        self.findings = []
        self.deck_rows = {}
        self.deck_filter = "ALL"
        self.last_file = ""
        self.last_file_wsl = ""
        self._chain_pending = False
        self._fprint_busy = False

        self._build()
        self._style_combos()
        self.sysmsg("%s %s - created by %s & %s" % (
            APP_NAME, APP_VER, CREATORS[0], CREATORS[1]))
        self.sysmsg("your lab. your gear. nothing here phones home.")
        self.select_tool(self.selected)
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

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        head = tk.Frame(self, bg=PANEL, height=70)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 8))
        head.grid_propagate(False)
        logo = tk.Canvas(head, width=44, height=44, bg=PANEL, highlightthickness=0)
        logo.create_oval(2, 2, 42, 42, outline=EDGE2)
        logo.create_polygon(25, 7, 14, 25, 21, 25, 18, 39, 31, 19, 23, 19, 27, 9,
                            fill=TURQ, outline="")
        logo.pack(side="left", padx=(10, 12))
        tt = tk.Frame(head, bg=PANEL)
        tt.pack(side="left")
        tk.Label(tt, text="HEXJACKED", bg=PANEL, fg=TXT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w")
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
        tk.Label(tt, text="five engines. one workbench. kali linux underneath.",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")
        self.net_btn = tk.Label(head, text="NETWORK SCAN", bg=PANEL2, fg=TURQ,
                                font=("Consolas", 9, "bold"), padx=10, pady=4, cursor="hand2")
        self.net_btn.pack(side="right", padx=(0, 8))
        self.net_btn.bind("<Button-1>", lambda e: self.open_networks())
        self.wsl_btn = tk.Label(head, text="WSL CONSOLE", bg=PANEL2, fg=BLUE,
                                font=("Consolas", 9, "bold"), padx=10, pady=4, cursor="hand2")
        self.wsl_btn.pack(side="right", padx=(0, 8))
        self.wsl_btn.bind("<Button-1>", lambda e: self.open_wsl_console())
        self.live_chip = tk.Label(head, text="STANDBY", bg=PANEL2, fg=DIM,
                                  font=("Consolas", 9, "bold"), padx=12, pady=4)
        self.live_chip.pack(side="right")

        rail = tk.Frame(self, bg=BG)
        rail.grid(row=1, column=0, sticky="nsew", padx=(14, 6))
        tk.Label(rail, text="ENGINES", bg=BG, fg=DIM,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 6))
        self.tiles = {}
        for k in TOOL_ORDER:
            tile = Tile(rail, self, k)
            tile.pack(fill="x", pady=4, ipady=2)
            self.tiles[k] = tile
        self.repair_btn = tk.Label(rail, text="FIX / INSTALL ENGINES", bg=PANEL2, fg=BLUE,
                                   font=("Consolas", 9, "bold"), padx=8, pady=8, cursor="hand2")
        self.repair_btn.pack(fill="x", pady=(12, 4))
        self.repair_btn.bind("<Button-1>", lambda e: self.install_engines())
        tk.Label(rail, text="your lab. your gear.", bg=BG, fg=DIM,
                 font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(6, 0))

        right = tk.Frame(self, bg=BG)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 14))
        right.rowconfigure(2, weight=6)
        right.rowconfigure(3, weight=2)
        right.columnconfigure(0, weight=1)

        bar = tk.Frame(right, bg=PANEL)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(bar, text=" ENGINE", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=8)
        self.toolvar = tk.StringVar(value=TOOLS[self.selected]["name"])
        self.toolbox = ttk.Combobox(bar, textvariable=self.toolvar, state="readonly",
                                    values=[TOOLS[k]["name"] for k in TOOL_ORDER], width=11)
        self.toolbox.pack(side="left", padx=(4, 0), pady=8)
        self.toolbox.bind("<<ComboboxSelected>>", lambda e: self._on_toolbox())
        tk.Label(bar, text="  COMMAND", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.cmdvar = tk.StringVar(value=TOOLS[self.selected]["preset"])
        self.cmdbox = ttk.Combobox(bar, textvariable=self.cmdvar, width=46)
        self.cmdbox.pack(side="left", fill="x", expand=True, padx=(4, 4), pady=8)
        self.browse_btn = tk.Label(bar, text=" BROWSE ", bg=PANEL2, fg=TURQ,
                                   font=("Consolas", 9, "bold"), padx=8, pady=5,
                                   cursor="hand2")
        self.browse_btn.pack(side="left", pady=8)
        self.browse_btn.bind("<Button-1>", lambda e: self.browse_target())
        self.dash_btn = tk.Label(bar, text=" DASHBOARD ", bg=PANEL2, fg=BLUE,
                                 font=("Consolas", 9, "bold"), padx=8, pady=5,
                                 cursor="hand2")
        self.dash_btn.pack(side="left", padx=(4, 0), pady=8)
        self.dash_btn.bind("<Button-1>", lambda e: self.open_dashboard())
        self.run_btn = tk.Label(bar, text=" RUN ", bg=blend(TURQ, BG, 0.82), fg=BG,
                                font=("Consolas", 11, "bold"), padx=16, pady=5, cursor="hand2")
        self.run_btn.pack(side="left", padx=2)
        self.run_btn.bind("<Button-1>", lambda e: self.run_selected())
        self.stop_btn = tk.Label(bar, text=" STOP ", bg=PANEL2, fg=DIM,
                                 font=("Consolas", 11, "bold"), padx=14, pady=5, cursor="hand2")
        self.stop_btn.pack(side="left", padx=(2, 10))
        self.stop_btn.bind("<Button-1>", lambda e: self.stop_selected())

        stages = tk.Frame(right, bg=PANEL)
        stages.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        tk.Label(stages, text=" FLOW", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=8)
        self.stage_lamps = {}
        for i, k in enumerate(TOOL_ORDER):
            nm = TOOLS[k]["name"].split(" - ")[0].upper()
            lamp = tk.Label(stages, text=" %d %s " % (i + 1, nm),
                            bg=PANEL2, fg=DIM, font=("Consolas", 9, "bold"),
                            padx=8, pady=4)
            lamp.pack(side="left", padx=(8, 0), pady=8)
            self.stage_lamps[k] = lamp

        deckwrap = tk.Frame(right, bg=EDGE2, highlightthickness=1,
                            highlightbackground=EDGE2)
        deckwrap.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        deckwrap.rowconfigure(2, weight=1)
        deckwrap.columnconfigure(0, weight=1)
        dhead = tk.Frame(deckwrap, bg=PANEL)
        dhead.grid(row=0, column=0, sticky="ew")
        tk.Label(dhead, text=" FINDINGS DECK", bg=PANEL, fg=TURQ,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=6)
        self.deck_chip = tk.Label(dhead, text="0 rows", bg=PANEL2, fg=DIM,
                                  font=("Consolas", 8, "bold"), padx=8, pady=1)
        self.deck_chip.pack(side="left", pady=6)
        self.deck_filters = {}
        for name in ("ALL", "FIND", "POL"):
            chip = tk.Label(dhead, text=" " + name + " ", bg=PANEL2, fg=DIM,
                            font=("Consolas", 8, "bold"), padx=6, pady=1,
                            cursor="hand2")
            chip.pack(side="left", padx=(4, 0), pady=6)
            chip.bind("<Button-1>", lambda e, n=name: self._deck_filter(n))
            self.deck_filters[name] = chip
        self.chain_btn = tk.Label(dhead, text=" AUTO CHAIN ", bg=blend(TURQ, BG, 0.82),
                                  fg=BG, font=("Consolas", 9, "bold"), padx=10,
                                  pady=6, cursor="hand2")
        self.chain_btn.pack(side="right", padx=(4, 2), pady=6)
        self.chain_btn.bind("<Button-1>", lambda e: self._auto_chain())
        self.open_src_btn = tk.Label(dhead, text=" OPEN SOURCE ", bg=PANEL2, fg=BLUE,
                                     font=("Consolas", 9, "bold"), padx=10, pady=6,
                                     cursor="hand2")
        self.open_src_btn.pack(side="right", padx=(4, 0), pady=6)
        self.open_src_btn.bind("<Button-1>", lambda e: self._open_source())
        self.deck_clear_btn = tk.Label(dhead, text=" CLEAR ", bg=PANEL2, fg=DIM,
                                       font=("Consolas", 9, "bold"), padx=8,
                                       pady=6, cursor="hand2")
        self.deck_clear_btn.pack(side="right", pady=6)
        self.deck_clear_btn.bind("<Button-1>", lambda e: self._deck_clear())
        self.fp_chip = tk.Label(
            deckwrap,
            text=" no file browsed yet - BROWSE arms the chain and fingerprints it",
            bg=PANEL, fg=DIM, anchor="w", font=("Consolas", 8))
        self.fp_chip.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
        decksplit = tk.Frame(deckwrap, bg=BG)
        decksplit.grid(row=2, column=0, sticky="nsew", padx=10, pady=(2, 10))
        decksplit.columnconfigure(0, weight=3, minsize=440)
        decksplit.columnconfigure(1, weight=1, minsize=300)
        decksplit.rowconfigure(0, weight=1)
        self.deck = ttk.Treeview(decksplit,
                                 columns=("sev", "rule", "file", "ln", "match"),
                                 show="headings", style="Deck.Treeview", height=6)
        for cid, txt, w in (("sev", "SEV", 80), ("rule", "RULE", 140),
                            ("file", "FILE", 170), ("ln", "LN", 40),
                            ("match", "MATCH", 180)):
            self.deck.heading(cid, text=txt)
            self.deck.column(cid, width=w, anchor="w",
                             stretch=(cid in ("file", "match")))
        dvsb = ttk.Scrollbar(decksplit, orient="vertical", command=self.deck.yview)
        dhsb = ttk.Scrollbar(decksplit, orient="horizontal", command=self.deck.xview)
        self.deck.configure(yscrollcommand=dvsb.set, xscrollcommand=dhsb.set)
        self.deck.grid(row=0, column=0, sticky="nsew")
        dvsb.grid(row=0, column=1, sticky="ns")
        dhsb.grid(row=1, column=0, sticky="ew")
        self.deck.bind("<<TreeviewSelect>>", self._on_deck_select)
        self.deck.bind("<Double-Button-1>", self._on_deck_dbl)
        viewwrap = tk.Frame(decksplit, bg=PANEL)
        viewwrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        vhead = tk.Frame(viewwrap, bg=PANEL)
        vhead.pack(fill="x")
        tk.Label(vhead, text="FINDING CONTENT", bg=PANEL, fg=TURQ,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=4)
        self.view_chip = tk.Label(vhead, text="empty", bg=PANEL2, fg=DIM,
                                  font=("Consolas", 8), padx=6, pady=1)
        self.view_chip.pack(side="left", padx=6)
        vacts = tk.Frame(viewwrap, bg=PANEL)
        vacts.pack(fill="x", pady=(0, 4))
        for txt, fn, col in (("COPY TEXT", self._copy_finding_text, TURQ),
                             ("COPY PATH", self._copy_finding_path, BLUE),
                             ("OPEN FILE", self._open_finding_file, BLUE)):
            b = tk.Label(vacts, text=" " + txt + " ", bg=PANEL2, fg=col,
                         font=("Consolas", 8, "bold"), padx=8, pady=3,
                         cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, f=fn: f())
        self.viewer = tk.Text(viewwrap, bg=PANEL, fg=TXT, wrap="word",
                              insertbackground=TURQ, relief="flat", bd=0,
                              font=("Consolas", 9), width=42, height=5,
                              state="disabled")
        self.viewer.pack(fill="both", expand=True)
        self.viewer.tag_configure("hdr", foreground=TURQ,
                                  font=("Consolas", 9, "bold"))
        self.viewer.tag_configure("err", foreground=RED)
        self.viewer.tag_configure("wrn", foreground=AMBER)
        self.viewer.tag_configure("dim", foreground=DIM)
        self.viewer.tag_configure("body", foreground=TXT)
        self.viewer.configure(state="normal")
        self.viewer.insert("end", "click a deck row - the matched code line\n"
                           "and the why behind it opens here", "dim")
        self.viewer.configure(state="disabled")

        conwrap = tk.Frame(right, bg=EDGE2, highlightthickness=1,
                           highlightbackground=EDGE2)
        conwrap.grid(row=3, column=0, sticky="nsew")
        self.console = tk.Text(conwrap, bg=PANEL, fg=TXT, wrap="none",
                               insertbackground=TURQ, selectbackground=BLUE,
                               font=("Consolas", 10), bd=0, padx=12, pady=8,
                               height=10, state="disabled", relief="flat")
        csb = ttk.Scrollbar(conwrap, command=self.console.yview)
        self.console.configure(yscrollcommand=csb.set)
        self.console.pack(fill="both", expand=True, side="left")
        csb.pack(fill="y", side="right")
        self.console.tag_configure("time", foreground=DIM)
        self.console.tag_configure("ok", foreground=GREEN)
        self.console.tag_configure("err", foreground=RED)
        self.console.tag_configure("warn", foreground=AMBER)
        self.console.tag_configure("sys", foreground=TURQ)
        self.console.tag_configure("input", foreground=BLUE,
                                   font=("Consolas", 10, "bold"))

        talk = tk.Frame(right, bg=PANEL)
        talk.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.talk_lbl = tk.Label(talk, text=" TALK TO %s " % TOOLS[self.selected]["name"],
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

        meters = tk.Frame(right, bg=BG)
        meters.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.g_cpu = Gauge(meters, "HOST CPU", TURQ)
        self.g_cpu.pack(side="left")
        self.g_ram = Gauge(meters, "HOST RAM", BLUE)
        self.g_ram.pack(side="left", padx=(6, 0))
        self.g_out = Gauge(meters, "OUT RATE", GREEN,
                           fmtfn=lambda v: fmt_bytes(v) + "/s")
        self.g_out.pack(side="left", padx=(6, 0))
        self.g_jobs = Gauge(meters, "ACTIVE JOBS", AMBER, fmt="%d")
        self.g_jobs.pack(side="left", padx=(6, 0))
        self.chart = Sparkline(meters, TURQ)
        self.chart.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.statusbar = tk.Label(self, text="", bg=PANEL, fg=DIM, anchor="w",
                                  font=("Segoe UI", 8), padx=12, pady=4)
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 10))

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
        style.configure("Net.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TXT, rowheight=26, borderwidth=0)
        style.configure("Net.Treeview.Heading", background=PANEL2, foreground=DIM,
                        relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Net.Treeview",
                  background=[("selected", blend(TURQ, BG, 0.7))],
                  foreground=[("selected", BG)])
        style.configure("Deck.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TXT, rowheight=24, borderwidth=0)
        style.configure("Deck.Treeview.Heading", background=PANEL2, foreground=DIM,
                        relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Deck.Treeview",
                  background=[("selected", blend(TURQ, BG, 0.7))],
                  foreground=[("selected", BG)])

    # ---------- console ----------
    def console_append(self, tool_key, text, tag=None):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if tag is None and tool_key:
            low = text.lower()
            if re.search(r"\b(error|fatal|failed|failure)\b", low):
                tag = "err"
            elif re.search(r"\b(warning|denied|refused)\b", low):
                tag = "warn"
        prefix = "[%s] %-11s" % (now, TOOLS[tool_key]["name"].upper()) if tool_key \
            else "[%s] " % now
        self.console.configure(state="normal")
        self.console.insert("end", prefix, "time" if not tool_key else "time")
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
                elif kind == "exit":
                    _, key, rc = item
                    job = self.jobs.pop(key, None)
                    t = self.tiles[key]
                    if job is not None and job.stopped:
                        t.status_kind = "stopped"
                    elif rc == 0:
                        t.status_kind = "done"
                    else:
                        t.status_kind = "fail"
                        t.rc = rc
                    self.sysmsg("%s engine finished (exit %s)" % (TOOLS[key]["name"], rc))
                    if job is not None and not job.stopped:
                        if key == "jadx" and getattr(self, "_chain_pending", False):
                            self._chain_pending = False
                            self.sysmsg("auto chain finished - pulling findings "
                                        "json from the box...")
                            self.fetch_findings()
                        elif key == "mobsfscan" and "--json" in job.cmdline:
                            self.sysmsg("mobsfscan --json finished - pulling "
                                        "findings json...")
                            self.fetch_findings()
                elif kind == "fprint":
                    self._apply_fprint(item[1])
                elif kind == "findings":
                    self._apply_findings(item[1])
                elif kind == "probe":
                    self.probe_running = False
                    self._apply_probe(item[1])
                elif kind == "msg":
                    self.sysmsg(item[1])
                elif kind == "netscan":
                    _, entries, stamp, silent = item
                    self._netscan_done(entries, stamp, silent)
        except queue.Empty:
            pass
        self.after(80, self._drain)

    # ---------- sensors ----------
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
        for t in self.tiles.values():
            t.paint()
        for key, job in self.jobs.items():
            el = int(time.time() - job.t0)
            self.tiles[key].elapsed = "%02d:%02d" % (el // 60, el % 60)
        if self.jobs:
            self.live_chip.configure(text="LIVE x%d" % len(self.jobs),
                                     bg=blend(TURQ, BG, 0.8), fg=BG)
        else:
            self.live_chip.configure(text="STANDBY", bg=PANEL2, fg=DIM)
        self.refresh_stages()
        self.stop_btn.configure(fg=RED if self.jobs.get(self.selected) else DIM)
        self.statusbar.configure(
            text="%s %s  -  %s & %s   |   distro: %s   |   lines: %d   |   total out: %s   |   logs: %s" % (
                APP_NAME, APP_VER, CREATORS[0], CREATORS[1], DISTRO,
                self.lines_out, fmt_bytes(self.out_bytes), self.logs_dir))
        self.after(60, self._tick_ui)

    # ---------- actions ----------
    def select_tool(self, key):
        if key not in TOOLS:
            self.sysmsg("tool not in this rack: %s" % key)
            return
        self.selected = key
        self.toolvar.set(TOOLS[key]["name"])
        self.talk_lbl.configure(text=" TALK TO %s " % TOOLS[key]["name"])
        self.cmdbox["values"] = tuple(TOOLS[key].get("presets") or (TOOLS[key]["preset"],))
        if not self.jobs.get(key):
            self.cmdvar.set(TOOLS[key]["preset"])

    def _on_toolbox(self):
        name = self.toolvar.get()
        for k, t in TOOLS.items():
            if t["name"] == name:
                self.select_tool(k)
                return

    def run_selected(self):
        key = self.selected
        if self.jobs.get(key):
            self.sysmsg("%s is already running - STOP it first" % TOOLS[key]["name"])
            return
        cmdline = self.cmdvar.get().strip()
        if not cmdline:
            self.sysmsg("command is empty")
            return
        if re.search(r"<[^>]+>", cmdline):
            self.sysmsg("unfilled <placeholder> - BROWSE loads a file into the "
                        "command, or edit it by hand")
            return
        job = Job(key, cmdline, self)
        self.jobs[key] = job
        t = self.tiles[key]
        t.status_kind = "run"
        t.rc = None
        t.elapsed = "00:00"
        job.start()
        self.sysmsg("LAUNCHED %s:  %s" % (TOOLS[key]["name"], cmdline))

    def stop_selected(self):
        job = self.jobs.get(self.selected)
        if not job:
            return
        job.stop()
        self.sysmsg("STOP sent to %s" % TOOLS[self.selected]["name"])

    def talk_send(self):
        key = self.selected
        line = self.talkvar.get().strip()
        if not line:
            return
        job = self.jobs.get(key)
        if job is None:
            self.sysmsg("%s is not running - RUN it first, then type to it here"
                        % TOOLS[key]["name"])
            return
        if job.send(line):
            self.console_append(key, ">>> %s\n" % line, tag="input")
            self.talkvar.set("")
        else:
            self.sysmsg("cannot send - %s window is closing" % TOOLS[key]["name"])

    def open_wsl_console(self):
        try:
            subprocess.Popen([WSL_EXE, "-d", DISTRO],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            self.sysmsg("cannot open wsl console: %s" % e)

    def browse_target(self):
        p = filedialog.askopenfilename(
            title="pick target file (apk / dex / zip / hashes)")
        if not p:
            return
        wp = to_wsl_path(p)
        cur = self.cmdvar.get()
        if re.search(r"<[^>]+>", cur):
            self.cmdvar.set(re.sub(r"<[^>]+>", wp, cur, count=1))
        else:
            self.cmdvar.set(cur + ' "' + wp + '"')
        self.sysmsg("target loaded: %s" % wp)
        self.last_file = p
        self.last_file_wsl = wp
        self.fingerprint(wp)

    def open_dashboard(self):
        running = self.jobs.get("mobsf") is not None
        try:
            webbrowser.open("http://localhost:8000")
            if running:
                self.sysmsg("MobSF dashboard: http://localhost:8000 - server RUNNING")
            else:
                self.sysmsg("MobSF dashboard: http://localhost:8000 - "
                            "RUN the MobSF server tile first for live access")
        except Exception as e:
            self.sysmsg("cannot open dashboard: %s" % e)

    def refresh_stages(self):
        for k, lamp in self.stage_lamps.items():
            job = self.jobs.get(k)
            t = self.tiles[k]
            if job is not None and t.status_kind == "run":
                lamp.configure(bg=BLUE, fg=PANEL)
            elif job is not None and t.status_kind == "exit" and (t.rc or 0) == 0:
                lamp.configure(bg=TURQ, fg=PANEL)
            else:
                lamp.configure(bg=PANEL2, fg=DIM)

    # ---------- findings deck ----------
    def _deck_filter(self, name):
        self.deck_filter = name
        self._deck_render("filter " + name)

    def _deck_filter_colors(self):
        for n, chip in self.deck_filters.items():
            chip.configure(fg=TURQ if n == self.deck_filter else DIM)

    def _deck_load(self, rows, label):
        self.findings = rows
        self._deck_render(label)

    def _deck_render(self, label):
        self.deck_rows = {}
        self.deck.delete(*self.deck.get_children())
        rows = self.findings
        if self.deck_filter == "FIND":
            rows = [r for r in rows if r["files"]]
        elif self.deck_filter == "POL":
            rows = [r for r in rows if not r["files"]]
        for i, f in enumerate(rows):
            iid = str(i)
            self.deck_rows[iid] = f
            self.deck.insert("", "end", iid=iid, values=finding_rowvals(f))
        nf = sum(1 for r in self.findings if r["files"])
        np = len(self.findings) - nf
        self.deck_chip.configure(text="%d rows (%d file / %d policy) - %s" % (
            len(rows), nf, np, label))
        self._deck_filter_colors()

    def _on_deck_select(self, _e=None):
        sel = self.deck.selection()
        if not sel or sel[0] not in self.deck_rows:
            return
        self._fill_viewer(self.deck_rows[sel[0]])

    def _on_deck_dbl(self, _e=None):
        return None

    def _deck_clear(self):
        self._deck_load([], "cleared")

    def _cur_finding(self):
        sel = self.deck.selection()
        if sel and sel[0] in self.deck_rows:
            return self.deck_rows[sel[0]]
        return None

    def _fill_viewer(self, f):
        self.viewer.configure(state="normal")
        self.viewer.delete("1.0", "end")
        if not f:
            self.viewer.insert("end", "click a deck row", "dim")
            self.viewer.configure(state="disabled")
            self.view_chip.configure(text="empty")
            return
        sevtag = "err" if f["sev"] in ("ERROR", "HIGH", "CRITICAL") else \
            ("wrn" if f["sev"] == "WARNING" else "dim")
        md = f.get("meta") or {}
        self.viewer.insert("end", "RULE  %s\n" % f["rule"], "hdr")
        self.viewer.insert("end", "SEV   %s\n" % f["sev"], sevtag)
        if md.get("owasp-mobile"):
            self.viewer.insert("end", "OWASP %s\n" % md.get("owasp-mobile"), "dim")
        if md.get("masvs"):
            self.viewer.insert("end", "MASVS %s\n" % md.get("masvs"), "dim")
        if f.get("file"):
            self.viewer.insert("end", "FILE  %s   LINE %s\n" % (f["file"], f["ln"]),
                               "dim")
            self.viewer.insert("end", "UNC   %s\n" % wsl_unc(f["file"]), "dim")
        if f.get("match"):
            self.viewer.insert("end", "----- MATCHED LINE -----\n", "hdr")
            self.viewer.insert("end", f["match"].rstrip("\n") + "\n", "body")
        if f.get("msg"):
            self.viewer.insert("end", "----- WHY -----\n", "hdr")
            self.viewer.insert("end", f["msg"].rstrip("\n") + "\n", "body")
        if f.get("ref"):
            self.viewer.insert("end", "REF   %s\n" % f["ref"], "dim")
        self.viewer.configure(state="disabled")
        self.view_chip.configure(text=f["rule"][:30])

    def _copy_finding_text(self):
        f = self._cur_finding()
        if not f:
            self.sysmsg("pick a deck row first")
            return
        piece = f.get("match") or f.get("msg") or ""
        loc = ""
        if f.get("file"):
            loc = "\n%s: line %s" % (f["file"], f["ln"])
        self.clipboard_clear()
        self.clipboard_append("[%s %s] %s%s" % (f["sev"], f["rule"], piece, loc))
        self.sysmsg("copied finding text: %s" % f["rule"])

    def _copy_finding_path(self):
        f = self._cur_finding()
        if not f:
            self.sysmsg("pick a deck row first")
            return
        if not f.get("file"):
            self.sysmsg("policy finding - no file path to copy")
            return
        self.clipboard_clear()
        self.clipboard_append("%s: %s" % (f["file"], f["ln"]))
        self.sysmsg("copied path: %s:%s" % (f["file"], f["ln"]))

    def _open_finding_file(self):
        f = self._cur_finding()
        if not f:
            self.sysmsg("pick a deck row first")
            return
        if not f.get("file"):
            self.sysmsg("policy finding - no file to open")
            return
        unc = wsl_unc(f["file"])
        if not os.path.exists(unc):
            self.sysmsg("file not visible over wsl UNC: %s" % unc)
            return
        try:
            subprocess.Popen(["notepad.exe", unc],
                             creationflags=CREATE_NO_WINDOW)
            self.sysmsg("opened in notepad: %s" % unc)
        except Exception as e:
            self.sysmsg("open failed: %s" % e)

    def _open_source(self):
        unc = wsl_unc("/tmp/hexjacked-out")
        if not os.path.exists(unc):
            self.sysmsg("no decompiled tree on the box - run AUTO CHAIN first")
            return
        try:
            os.startfile(unc)
            self.sysmsg("opening decompiled sources: %s" % unc)
        except Exception as e:
            self.sysmsg("open source failed: %s" % e)

    def _auto_chain(self):
        apk = self.last_file_wsl
        if not apk:
            self.sysmsg("BROWSE an apk/dex/jar first - AUTO CHAIN decompiles it "
                        "then mobsfscans the decompiled sources into the deck")
            return
        if self.jobs.get("jadx"):
            self.sysmsg("JADX tile is busy - STOP it first, then chain")
            return
        cmdline = CHAIN_TEMPLATE.replace("<file>", apk)
        job = Job("jadx", cmdline, self)
        self.jobs["jadx"] = job
        t = self.tiles["jadx"]
        t.status_kind = "run"
        t.rc = None
        t.elapsed = "00:00"
        self._chain_pending = True
        job.start()
        self.sysmsg("AUTO CHAIN launched on %s: jadx decompile -> mobsfscan "
                    "--json over the sources -> findings deck" % apk)

    def fetch_findings(self):
        def work():
            rc, out = run_wsl_b64(FETCH_SCRIPT, 120)
            payload = None
            njava = None
            m = re.search(r"JSONB64=([A-Za-z0-9+/=]+)", out)
            if m:
                try:
                    payload = base64.b64decode(m.group(1)).decode("utf-8",
                                                                  "replace")
                except Exception:
                    payload = None
            mj = re.search(r"NJAVA=(\d+)", out)
            if mj:
                njava = int(mj.group(1))
            self.put(("findings", {"json": payload, "njava": njava, "rc": rc}))
        threading.Thread(target=work, daemon=True).start()

    def _apply_findings(self, d):
        rows = []
        payload = d.get("json")
        if payload:
            rows = parse_mobsfscan_json(payload)
        if d.get("njava") is not None:
            rows.append({"rule": "JADX-SUMMARY", "sev": "INFO", "rank": 0,
                         "file": "", "ln": "", "match": "", "meta": {},
                         "files": 0,
                         "msg": "auto chain: %d java sources decompiled"
                         % d["njava"], "ref": ""})
        self._deck_load(rows, "auto chain" if rows or d.get("njava")
                        else "no json on the box")
        if not rows:
            self.sysmsg("no findings json found - BROWSE the apk, then AUTO "
                        "CHAIN (decompile + scan in one run)")

    def fingerprint(self, wp):
        if not wp:
            return
        if self._fprint_busy:
            self.sysmsg("fingerprint busy - one file at a time")
            return
        self._fprint_busy = True
        name = self.last_file and os.path.basename(self.last_file) or wp
        if name and os.path.basename(name) == name:
            shown = name
        else:
            shown = wp
        self.fp_chip.configure(text=" fingerprinting %s ..." % shown)

        def work():
            rc, out = run_wsl_b64(FPRINT_SCRIPT % shq(wp), 60)
            d = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip()
            self._fprint_busy = False
            self.put(("fprint", d if d else {"ERR": out[-200:] or "rc=%d" % rc}))
        threading.Thread(target=work, daemon=True).start()

    def _apply_fprint(self, d):
        if d.get("ERR"):
            self.fp_chip.configure(
                text=" fingerprint failed: %s" % (d["ERR"][-160:],))
            return
        try:
            size = int(d.get("SIZE") or 0)
        except Exception:
            size = 0
        md5v = d.get("MD5") or ""
        shav = d.get("SHA256") or ""
        mime = d.get("MIME") or "?"
        name = self.last_file and os.path.basename(self.last_file) or "file"
        self.fp_chip.configure(text=" %s   %s   md5 %s..%s   sha256 %s..%s   %s" % (
            name, fmt_bytes(size), md5v[:12], md5v[-4:],
            shav[:12], shav[-4:], mime))

    # ---------- engines ----------
    def probe_engines(self):
        if self.probe_running:
            return
        self.probe_running = True
        for t in self.tiles.values():
            if t.status_kind == "idle":
                t.status_kind = "probe"
        self.sysmsg("checking engines inside %s ..." % DISTRO)

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
        self.sysmsg("engine check: %s" % json.dumps(results))
        probe_lane = {"jadx": "jadx", "mobsf": "mobsf-server", "frida": "frida",
                      "impacket": "impacket-smbclient", "hashcat": "hashcat"}
        for k in TOOL_ORDER:
            if k == "mobsf":
                srv = results.get("mobsf-server", "MISSING")
                cli = results.get("mobsfscan", "MISSING")
                if "MISSING" in srv and "MISSING" in cli:
                    ver = "MISSING"
                else:
                    ver = srv if "MISSING" not in srv else cli
            else:
                ver = results.get(probe_lane.get(k, TOOLS[k]["bin"]))
            t = self.tiles[k]
            if ver is None:
                t.status_kind = "idle"
                continue
            if "MISSING" in ver:
                t.status_kind = "missing"
            else:
                t.status_kind = "detect"
                t.ver = ver
        for k in TOOL_ORDER:
            self.tiles[k]._paint_chip()
        if any(t.status_kind == "missing" for t in self.tiles.values()):
            self.sysmsg("one or more engines missing - hit FIX / INSTALL ENGINES")

    def install_engines(self):
        slot = TOOL_ORDER[0]
        if self.jobs.get(slot):
            self.sysmsg("%s slot busy - STOP it first for a reinstall"
                        % TOOLS[slot]["name"])
            return
        self.sysmsg("INSTALL: apt %s + pip frida-tools/mobsfscan/rich-fix "
                    "(long haul - watch the stream)" % INSTALL_PKGS)
        script = ("export DEBIAN_FRONTEND=noninteractive; "
                  "apt-get update -y; "
                  "apt-get install -y --no-install-recommends %s; "
                  "pip3 install --break-system-packages frida-tools mobsfscan; "
                  "pip3 install --break-system-packages --quiet --upgrade "
                  "--user rich; "
                  "echo INSTALL_DONE_RC=$?" % INSTALL_PKGS)
        job = Job(slot, script, self)
        self.jobs[slot] = job
        t = self.tiles[slot]
        t.status_kind = "run"
        t.rc = None
        t.elapsed = "00:00"
        job.start()

    # ---------- networks ----------
    def open_networks(self):
        p = getattr(self, "netpanel", None)
        if p is not None:
            try:
                if p.winfo_exists():
                    p.deiconify()
                    p.lift()
                    return
            except Exception:
                pass
        self.netpanel = NetworkPanel(self)
        self.start_netscan()

    def start_netscan(self, silent=False):
        if self._scanning:
            return
        self._scanning = True
        if not silent:
            self.sysmsg("scanning wifi networks...")
        threading.Thread(target=self._netscan_work, args=(silent,), daemon=True).start()

    def _netscan_work(self, silent):
        try:
            p = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"],
                               capture_output=True, timeout=30,
                               creationflags=CREATE_NO_WINDOW)
            text = p.stdout.decode("utf-8", "replace")
            entries = parse_wlan_scan(text)
        except Exception as e:
            entries = []
            self.put(("msg", "wifi scan error: %s" % e))
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.put(("netscan", entries, stamp, silent))

    def _netscan_done(self, entries, stamp, silent):
        self._scanning = False
        p = getattr(self, "netpanel", None)
        if p is None:
            return
        try:
            if not p.winfo_exists():
                return
        except Exception:
            return
        p._apply(entries, stamp)
        if not silent:
            self.sysmsg("wifi scan: %d networks seen" % len(entries))

    def use_as_target(self, ssid):
        q = ('"%s"' % ssid) if (" " in ssid or "<" in ssid) else ssid
        cmd = self.cmdvar.get()
        if "<target>" in cmd:
            self.cmdvar.set(cmd.replace("<target>", q))
            self.sysmsg("target set: %s" % ssid)
        else:
            self.sysmsg('no <target> placeholder in the command box - add one, '
                        'or use ARM WIFITE')

    def arm_wifite(self, ssid):
        self.cmdvar.set('wifite --kill -e "%s"' % ssid)
        self.sysmsg('wireless preset set on "%s" - HEXJACKED rack has no wifite; '
                    'CrackerJacked cockpit runs that lane' % ssid)

    def aim_nmap(self):
        sub = get_lan_subnet()
        if not sub:
            self.sysmsg("could not find a LAN ipv4 for the /24 - check ipconfig")
            return
        self.cmdvar.set("nmap -T4 -A -v %s" % sub)
        self.sysmsg("nmap aimed at %s" % sub)

    def copy_bssid(self, mac):
        self.clipboard_clear()
        self.clipboard_append(mac)
        self.sysmsg("copied to clipboard: %s" % mac)


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
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
