# **XXxVector_SourcingxXX**

**CREATED BY XxREPTILExX & XxNEOPAULxX**

XXxVector_SourcingxXX v1.2.2 - the reconnaissance & OSINT command deck
(christened by zack 2026-11-18; first boot was as ReconJacked the same
night). A Windows GUI
that drives five scout engines inside the Kali Linux WSL distro
(`kali-linux`) and parses their live output into an interactive FINDINGS
DECK - every scraped item becomes a row you can click, pivot, export.
Complete build 2026-11-18 on PAUL-MOBILE.

## The five scouts, in run order

1. **Sherlock - Usernames** - hunts one handle across hundreds of social
   platforms at once. Every hit lands as a row; click it to open the live
   profile in your browser. Presets: full hunt, found-only, bare.
2. **theHarvester - Emails & Hosts** - pulls emails, subdomains, virtual
   hosts and open-port intel from search engines + PGP servers
   (bing + crtsh + otx bundle, or single sources). Sections stream into
   typed rows (EMAILS / HOSTS / CERTS...).
3. **Amass - Attack Surface** - OWASP passive mapping of a domain's
   external assets: subdomains, hostnames. Progress chatter stays in the
   console; clean FQDN assets land on the deck.
4. **ExifTool - Metadata** - every hidden field in images / PDFs / docs,
   with GPS stamps decoded to decimal coordinates (Google-Maps clickable).
   Presets: quick, full `-a -G1` grouped, exhaustive `-a -u -g1`.
5. **Gitleaks - Secrets** - scans a repo or a whole folder for hardcoded
   API keys / tokens. Rows carry the rule (aws-access-token, github-pat...),
   the file:line, and a MASKED secret - reveal only on purpose.

## The deck - all ports of interaction

- **THE HUNTERS rail** (left) - one tab per scout with a LIVE count badge.
  Click a tab to load its scout + command set.
- **FINDINGS DECK** - columns SCOUT / FINDING / VALUE / DETAIL. Filter chips
  (ALL / SHL / HRV / AMS / EXF / GLK) and a instant FILTER box cut the view;
  EXPORT saves everything (CSV or TXT TSV); CLEAR wipes with a confirm.
- **Right-click a row** - OPEN IN BROWSER (profiles, maps, any url row),
  COPY VALUE, REVEAL SECRET on a masked leak row (deliberate only),
  COPY RAW SECRET, or **PIVOT** - send the row's value straight into another
  scout's command (username -> Sherlock, domain -> theHarvester/Amass,
  file -> ExifTool, folder -> Gitleaks) and run the next leg from where you
  found the first clue.
- **TALK strip** - feeds stdin to the running scout, your lines echo blue.
- **BROWSE** - loads a real Windows file/folder; for Gitleaks picking a file
  scans the whole folder around it. Paths auto-convert to `/mnt/c/...`.

## Use steps

1. Run **XXxVector_SourcingxXX.exe**. Hunter tabs flip to DETECTED after the live
   engine check (first probe runs automatically).
2. Pick a hunter tab, pick a COMMAND preset.
3. **BROWSE** (or type) a target, **RUN** - the console streams raw engine
   chatter while the deck fills in real time with parsed findings.
4. FLOW lamps (SHL HRV AMS EXF GLK) light per engine stage - blue while
   running, turquoise when finished clean.
5. Right-click findings to pivot onward - that is the hunt.
6. `STOP` kills the engine inside WSL. `WSL CONSOLE` opens a full terminal.
7. `PULL MISSING SCOUTS` reruns the apt install for anything absent.

## Notes

- Everything runs in the WSL distro `kali-linux`; the deck parser streams
  the real output formats captured live on v110 (Sherlock 0.16,
  theHarvester 4.11.1, Amass 5.1.3, ExifTool 13.55, Gitleaks 8.26).
- Gitleaks allowlists AWS's printed example keys - use a real-shaped
  secret to test it; findings from `--verbose` blocks are what feed the deck.
- Raw logs land in `<exe folder>\logs` (falls back to
  `%APPDATA%\XXxVector_SourcingxXX\logs` when the exe folder is
  unwritable).
- your lab. your gear. nothing here phones home.
