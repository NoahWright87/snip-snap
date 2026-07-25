snip-snap - preview build
==========================

This is an automatically built preview of snip-snap from a pull request.
It is NOT signed, so Windows will likely show a "Windows protected your PC"
SmartScreen warning when you run it. That's expected for an unsigned indie
app, not a sign anything is wrong - click "More info", then "Run anyway".
For normal installs, use the release installer instead:
https://github.com/NoahWright87/snip-snap/releases/latest

To run:
  1. Double-click snip-snap.exe. No console/terminal window will appear.
  2. A standalone app window will open automatically after a moment (using
     Chrome or Edge in app mode - no address bar or tabs, just the app).

  First-run note:
    The app sets up ffmpeg in the background on first launch (one-time
    download, a hundred-ish MB). You can start marking cuts/keeps while that
    finishes; exporting waits until it's ready.

Your videos are read in place from wherever you point "Add folder" -
nothing is uploaded or copied anywhere. All data (which videos you've
added, your cut/keep decisions, tags) is stored locally in
%USERPROFILE%\.snip-snap\snip-snap.db, and the downloaded ffmpeg lives in
%USERPROFILE%\.snip-snap\ffmpeg_bin\ (shared across app updates - it won't
re-download every time you get a new preview build).

Troubleshooting: since there's no console window, logs go to
%USERPROFILE%\.snip-snap\logs\snip-snap.log instead - check there if
something doesn't seem to be working.
