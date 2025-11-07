# KiCad Companion (Windows-first)

Stand-alone companion app that stays **dormant** until KiCad is detected, then becomes an **active sync orchestrator** for library repos. 
Windows-first; Python; Qt overlay (always-on-top, click-through by default).

## Features (v0 skeleton)
- Endpoint detection (IPC path or process fallback)
- Overlay UI (PySide6) + tray
- File-system watch (watchdog) with debounce

## Quick start (dev)

```bash
# Python 3.11+ recommended
python -m venv .venv
. .venv/Scripts/activate

pip install -r requirements.txt

# Run
python -m companion.app.main
```

## Project layout
See `src/KiCadPartsSyncer/*` for modules. This is a **skeleton**—stubs are implemented where KiCad IPC specifics will be filled in later.
