# snip-snap

A locally-hosted video editor for trimming full-length videos down to the
good parts. Runs entirely on your own machine — no cloud APIs, no accounts,
no telemetry. It's a local web app: a Python backend serves both the API and
the UI on `localhost`, and you use it in your browser.

This is the core manual editing loop: ingest a folder, scrub the timeline and
snip (✂️) it into clips, mark the ones you don't want as deleted and tag them,
then export. Everything not marked deleted ends up in the final file - there's
no separate "keep" action. The ML-assisted suggestion pipeline described in
the original design doc is tracked separately as GitHub issues (#2–#6) and
not built yet.

## Requirements

- Python 3.11+
- Node.js 18+ (only needed to build the frontend)
- ffmpeg. On Windows, the app downloads and caches this itself on first run
  (see "ffmpeg setup" below) — nothing to install manually. On macOS/Linux
  (dev use only; the packaged app targets Windows), install it yourself and
  make sure it's on your `PATH`.

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

### ffmpeg setup

On Windows, if ffmpeg isn't already available, the app downloads a build in
the background on first launch and caches it in `~/.snip-snap/ffmpeg_bin/`
(one-time; later launches and later versions of the app reuse it). A banner
at the top of the UI shows progress — you can keep editing while it
downloads, export just waits until it's ready. Check
`GET /api/ffmpeg/status` directly, or `~/.snip-snap/logs/snip-snap.log` in
the packaged build, if something seems stuck.

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
copied. Each folder you add gets a `.snipsnap.json` file written into it
listing its videos and their segments/tags/decisions — that's the real
source of truth, so it travels with the videos if you move, copy, or back up
the folder. A small SQLite database under `~/.snip-snap/` (override with the
`SNIPSNAP_DATA_DIR` environment variable) just remembers which folders
you've added, so the library view knows where to look.

## Tests

```bash
cd backend
pytest
```

## Installing on Windows

Use the latest installer from GitHub Releases:

- https://github.com/NoahWright87/snip-snap/releases/latest

Download `snip-snap-setup-<version>.exe` and run it. New releases are
installed by running the next installer version; your app data stays under
`~/.snip-snap/`, so upgrades keep your library and editing state.

## Trying a pull request without setting up a dev environment

Every PR that touches `backend/` or `frontend/` gets a Windows preview build
via GitHub Actions (`.github/workflows/preview-build.yml`): a single
`snip-snap.exe` with the frontend baked in (ffmpeg downloads itself on first
run - see above - so the artifact stays small). The PR itself gets a comment
with a direct download link once the build finishes (or a link to the log if
it fails); the artifact is also always reachable under the PR's checks:
**Checks tab → "Preview Build (Windows)" → Summary → Artifacts**. Download
and unzip `snip-snap-preview-unsigned-pr<N>`, then double-click
`snip-snap-preview-setup.exe` (installer path) or `snip-snap.exe` (portable).
These preview artifacts are unsigned and meant for PR validation (not normal
end-user installs), so Windows SmartScreen may warn. See the bundled
`README.txt` for details.
