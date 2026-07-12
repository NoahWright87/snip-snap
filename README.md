# snip-snap

A locally-hosted video editor for trimming full-length videos down to the
good parts. Runs entirely on your own machine — no cloud APIs, no accounts,
no telemetry. It's a local web app: a Python backend serves both the API and
the UI on `localhost`, and you use it in your browser.

This is the core manual editing loop (ingest a folder → mark cut/keep
segments and tags → export). The ML-assisted suggestion pipeline described
in the original design doc is tracked separately as GitHub issues (#2–#6) and
not built yet.

## Requirements

- Python 3.11+
- Node.js 18+ (only needed to build the frontend)
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH` (used to read
  video durations and to export the trimmed file). Not preinstalled on
  Windows — download a build and add its `bin` folder to your PATH.

## Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
pip install -r requirements.txt

# Frontend (build once; the backend serves the built files)
cd ../frontend
npm install
npm run build
```

## Running

```bash
cd backend
python launcher.py
```

This starts the backend on `http://127.0.0.1:8756` and opens it automatically
in a standalone window (Chrome/Edge "app mode" if either is installed - no
address bar or tabs; otherwise a normal browser tab as a fallback). If it's
already running (e.g. you double-clicked the launcher twice), it just
opens/reuses the existing window instead of starting a second backend.

The backend shuts itself down automatically if the browser tab closes (or
crashes and stops sending its heartbeat), so you won't end up with orphaned
backend processes piling up across sessions.

### Frontend development

For live-reloading frontend changes instead of rebuilding on every edit, run
the backend as above and, in a second terminal:

```bash
cd frontend
npm run dev
```

and use the Vite dev server URL it prints (it proxies `/api` to the backend).

## Data

Videos are read in place from wherever you point "Add folder" — nothing is
copied. Metadata (ingested videos, segments, tags) lives in a SQLite database
under `~/.snip-snap/` by default (override with the `SNIPSNAP_DATA_DIR`
environment variable).

## Tests

```bash
cd backend
pytest
```

## Trying a pull request without setting up a dev environment

Every PR that touches `backend/` or `frontend/` gets a Windows preview build
via GitHub Actions (`.github/workflows/preview-build.yml`): a single
`snip-snap.exe` with the frontend *and ffmpeg* baked in — nothing else to
install to try it. The PR itself gets a comment with a direct download link
once the build finishes (or a link to the log if it fails); the artifact is
also always reachable under the PR's checks: **Checks tab → "Preview Build
(Windows)" → Summary → Artifacts**. Download and unzip
`snip-snap-preview-pr<N>`, then double-click `snip-snap.exe` — no console
window, no browser tab, just an app window. Windows SmartScreen will likely
warn since it's unsigned — that's expected for an unsigned build, click "More
info" → "Run anyway". See the bundled `README.txt` for details.
