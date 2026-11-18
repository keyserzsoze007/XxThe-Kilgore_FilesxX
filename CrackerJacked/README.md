# CrackerJacked — five engines, one cockpit

**CREATED BY XxREPTILExX & XxNEOPAULxX**

CrackerJacked v1.1.4 — a Windows GUI that drives Metasploit, Nmap, Wifite2,
Bettercap and Responder, all running inside the Kali Linux WSL distro
(`kali-linux`). Built 2026-11-18 on PAUL-MOBILE.

## Created by
- **XxREPTILExX** — direction, targets, the name (zack)
- **XxNEOPAULxX** — design and build (Paul Kilgore 3rd)

## Files
- `dist\CrackerJacked.exe` — the program (onefile, windowed, ~10.6 MB)
- `crackerjacked.py` — single-file source (Python 3.12 + tkinter)
- `icon.ico` / `icon.png` / `icon.svg` — the bolt-crack mark
- `logs\` — per-tool + session logs (written next to the exe, falls back to %APPDATA%)
- Desktop: `CrackerJacked.lnk`, `CrackerJacked Console.lnk` (raw WSL Kali shell)

## Use
1. Click an engine tile (left rail) to load its preset command.
2. Edit the command box (replace `<target>` with an IP/subnet).
3. RUN — output streams live into the console; meters animate on the right.
4. STOP kills the engine inside WSL (`pkill`) then drops the wrapper.
5. TALK strip (under the console) — type a line, ENTER sends it to the
   running engine's stdin: msf commands, Bettercap prompts, Wifite's target
   picker. Sent lines echo as blue `>>> ` lines.
6. `WSL CONSOLE` opens a full interactive Kali shell (full keyboard terminal).

## Network selector (v1.1)
The `NETWORK SCAN` chip in the header opens the picker panel:
- Scans APs via `netsh wlan show networks mode=bssid` — Windows side,
  no elevation. Auto-refreshes every 6s while the panel is open.
- Rows accumulate for 120s (v1.1.4): when the Wi-Fi driver parks its
  background scans (it does while connected on a 5GHz link), the panel
  keeps showing everything seen recently instead of collapsing to the
  one network on the current channel. SIGNAL column carries the row age
  (`now` when just heard, `12s` when remembered).
- Rows show SSID, ASCII signal bars, channel(s), auth, strongest BSSID.
- **USE AS TARGET** replaces `<target>` in the command box with the SSID.
- **ARM WIFITE** selects Wifite2 and sets `wifite --kill -e "<ssid>"`.
- **AIM NMAP AT LAN** derives the /24 from ipconfig and sets an aggressive
  host sweep (`192.168.x.0/24` preferred).
- **COPY BSSID** puts the strongest AP's MAC on the clipboard.

## Engines (verified 2026-11-18)| Engine | Version | Note |
|---|---|---|
| Metasploit | 6.5.7-dev | `msfconsole -q`; DB = postgresql installed |
| Nmap | 7.991 | |
| Wifite2 | 2.8.2 | needs a monitor-mode-capable adapter |
| Bettercap | 2.41.5 | |
| Responder | 3.2.2.0-0kali2 | `-I eth0`; eth0 = WSL default adapter |

## Notes
- Metasploit default preset is now interactive: `msfconsole -q` boots, then
  you drive it from the TALK strip (`version`, `db_status`, `search ...`,
  `exit`). The batch `-x "<cmds>; exit"` presets stay in the dropdown for
  one-shots that must not linger.
- The console display filters the `stty: Inappropriate ioctl` noise that
  engines emit on pipes (raw logs keep everything).
- Wifite2 runs under a pseudo-TTY (`script -qec '...' /dev/null`) because it
  needs `stty size`. Headless runs want a concrete target — the cockpit's
  preset is `wifite --kill -e "<ssid>"`; NETWORK SCAN → ARM WIFITE fills it.
  Or run bare `wifite --kill` and type the target NUMBER into the TALK strip
  when the target table appears.
- Engines run in batch mode through pipes with stdin wired for the TALK
  strip; the TALK strip works for both plain-pipe and pseudo-TTY engines.
- "FIX / INSTALL ENGINES" re-runs the apt installer if anything goes missing.
- Engine check runs automatically at launch (tiles flip to DETECTED).
