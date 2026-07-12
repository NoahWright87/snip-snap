snip-snap - preview build
==========================

This is an automatically built preview of snip-snap from a pull request.
It is NOT signed, so Windows will likely show a "Windows protected your PC"
SmartScreen warning when you run it. That's expected for an unsigned indie
app, not a sign anything is wrong - click "More info", then "Run anyway".

To run:
  1. Double-click snip-snap.exe. No console/terminal window will appear.
  2. A standalone app window will open automatically after a moment (using
     Chrome or Edge in app mode - no address bar or tabs, just the app).
  3. To quit, close that window - the app shuts itself down automatically.

ffmpeg is bundled - nothing else to install. (License in FFMPEG_LICENSE.txt.)

Your videos are read in place from wherever you point "Add folder" -
nothing is uploaded or copied anywhere. All data (which videos you've
added, your cut/keep decisions, tags) is stored locally in
%USERPROFILE%\.snip-snap\snip-snap.db

Troubleshooting: since there's no console window, logs go to
%USERPROFILE%\.snip-snap\logs\snip-snap.log instead - check there if
something doesn't seem to be working.
