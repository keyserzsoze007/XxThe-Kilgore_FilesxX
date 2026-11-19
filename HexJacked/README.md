# HEXJACKED

**CREATED BY XxREPTILExX & XxNEOPAULxX**

HexJacked v1.1.0 - the mobile & binary workbench. A Windows GUI that drives
five engines inside the Kali Linux WSL distro (`kali-linux`), in engagement
order, with live streaming console, meters, and an interactive TALK strip.
Built 2026-11-18 on PAUL-MOBILE. v1.1.0 (2026-11-19): FINDINGS DECK upgrade -
AUTO CHAIN (one click decompiles your APK then static-scans the decompiled
sources), every finding clickable into a FINDING CONTENT viewer, per-file
fingerprints (size / md5 / sha256 / mime) on BROWSE, and a self-healing
rich fix baked into FIX / INSTALL ENGINES (the shadowed user-level rich
that starved mobsfscan's file-level scans on this box is upgraded during
install).

## The five, in run order

1. **JADX - Decompile** - APK/DEX -> Java source (`jadx`), resource decode
   (`apktool`). Presets for source + bad-code + apktool.
2. **MobSF - Static Scan** - MobSF server mode (dashboard at
   http://localhost:8000 via the DASHBOARD button - WSL forwards the port)
   plus the fast CLI static scanner `mobsfscan`.
3. **Frida - Live Hooks** - dynamic instrumentation: list apps (`frida-ps
   -U`), trace (`frida-trace -U -f <package>`), attach a REPL with your own
   script (`frida -U -f <package> -l <script.js>`).
4. **Impacket - Network** - AD/SMB/lateral: `impacket-smbclient`,
   `impacket-secretsdump`, `impacket-psexec`, `impacket-getuserspns`.
5. **Hashcat - Crack** - password recovery on CPU OpenCL: benchmark
   (`hashcat -b -m 0`) or point `<hashes.txt>` at rockyou (modes 0 / 1000 /
   22000).

## Use steps

1. Run **HexJacked.exe**. Tiles flip to DETECTED
   after the live engine check (first probe runs automatically).
2. Pick an engine tile, pick a preset from the COMMAND dropdown.
3. **BROWSE** loads a real file (APK, dex, zip, hashes) - it converts the
   Windows path to `/mnt/c/...` and fills its `<placeholder>` in the command.
4. **RUN**. The console streams while it works; **FLOW** lamps light up per
   stage (blue = running, turquoise = finished clean).
5. **AUTO CHAIN** (deck head, one click): decompiles the BROWSEd APK into
   `/tmp/hexjacked-out`, then `mobsfscan --json` scans the decompiled
   sources - findings land in the **FINDINGS DECK**. Click a row: the
   matched code line plus the why behind it open in **FINDING CONTENT**
   (COPY TEXT / COPY PATH / OPEN FILE). Filter chips ALL / FIND / POL.
6. **OPEN SOURCE** jumps Windows Explorer into the decompiled tree
   (`\\wsl.localhost\kali-linux\tmp\hexjacked-out`).
7. **TALK strip** (under the console) sends stdin into the running engine -
   Frida REPL, impacket sessions, MobSF prompts. Your lines echo blue.
8. **DASHBOARD** opens the MobSF web UI (start the MobSF server tile first).
9. `STOP` kills the engine inside WSL. `WSL CONSOLE` opens a full terminal.
10. `FIX / INSTALL ENGINES` reruns apt + pip install if anything is missing
    (includes the rich fix that keeps mobsfscan's file-level scans alive).

## Notes

- Engines run in the WSL distro `kali-linux`. Frida and Impacket run under a
  pseudo-TTY (`script -qec`) so their interactive prompts work; the TALK
  strip drives both pipe and pty engines.
- Hashcat on this box runs on CPU OpenCL (pocl). GPU cracking wants the
  Windows GPU rigs - this is the portable lane.
- WPA targets: hashcat mode 22000 takes hc22000 format (hash:mic pairs from
  hcxtools).
- Windows-side Wi-Fi scanning: the NETWORK SCAN panel reads netsh (no
  elevation) and accumulates rows for 120s.
- Raw logs land in `%APPDATA%\HexJacked\logs`.
- your lab. your gear. nothing here phones home.
