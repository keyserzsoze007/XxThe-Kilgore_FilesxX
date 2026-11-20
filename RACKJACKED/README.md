# RACKJACKED v1.0.0

One rack, every tool. A single-window catalog over the whole tool list -
167 entries, 11 categories, the full flag system, and live detection of
what is already installed on this machine.

CREATED BY  XxREPTILExX  x  XxNEOPAULxX

## What it does

- **One table, every tool.** Name, flags, OS compatibility and live status.
- **Live search.** Type anywhere in the name, category, description or flags.
- **Flag filter.** The chips under the toolbar stack as AND filters: pick
  `G` + `C` and you get open-source CLI tools only; pick `I` for web services.
- **Category pane** with per-category counts.
- **Status column** comes from an actual probe of this box:
  - `FOUND` - the binary or Python module resolves (turquoise)
  - `WEB`   - website entry, opens in the browser
  - `REPO`  - git project, link goes to the repository
  - `MANUAL` - commercial / manual install
- **Detail pane** shows the description, the expanded meaning of every flag,
  the URL, and one-click `OPEN LINK` / `COPY LINK` / `COPY NAME` / `COPY CMD`.
- **RESCAN** re-probes the toolchain without restarting.
- Double-click a row to open its link. `Ctrl+F` search, `Esc` reset.

## Flag key

| Flag | Meaning |
|------|---------|
| G | GitHub / git repository (implies open source) |
| S | Commercial software - not always free, may be restrictive |
| F | Freeware - free to use, not necessarily open source |
| I | Website |
| P | Chrome plugin |
| R | Firefox plugin |
| D | IDA Pro plugin |
| C | CLI tool |
| O | Open source |
| M | Miscellaneous |
| L | Linux compatible |
| W | Windows compatible |

`L` and `W` are reverse flags: they are set only when that platform is
supported, so no mark at all means "neither listed".

## Layout

```
C:\Work\projects\rackjacked\
    catalog.py        data - 167 entries, categories, flag meanings
    rackjacked.py     the application
    smoke_test.py     catalog validation + every filter path
    RACKJACKED.spec   PyInstaller build spec
    build\            PyInstaller work dir

C:\Work\tools\rackjacked\
    RACKJACKED.exe    shipped build, ~11.5 MB, no runtime deps
```

## Build

```
python -m PyInstaller --noconfirm --onefile --windowed --name RACKJACKED ^
    --distpath C:\Work\tools\rackjacked ^
    --workpath C:\Work\projects\rackjacked\build ^
    --specpath C:\Work\projects\rackjacked rackjacked.py
```

## Test

```
python smoke_test.py
```

Validates every catalog row (required keys, known category, known flags,
http URLs, no duplicate names) and then drives the window through category
filter, flag filter, search, detail render, reset and both sort directions.

## Adding a tool

Append one dict to `TOOLS` in `catalog.py`:

```python
dict(n="toolname", c="Web", f="GC", d="what it does",
     u="https://github.com/author/tool", b=["toolname"], x="toolname --help")
```

`b` is the list of binaries or Python modules to probe for; `x` is an
example command that `COPY CMD` hands back. Then update `APP_VER`, rebuild.
