snip-snap - preview build
==========================

This is an automatically built preview of snip-snap from a pull request.
It is NOT signed, so Windows will likely show a "Windows protected your PC"
SmartScreen warning when you run it. That's expected for an unsigned indie
app, not a sign anything is wrong - click "More info", then "Run anyway".

To run:
  1. Double-click snip-snap.exe.
  2. A browser window will open to the app automatically after a moment.
  3. To quit, just close the browser tab/window - the app shuts itself down.

Requirements:
  - ffmpeg must be installed separately and on your PATH for exporting
    videos and reading video durations. Get it from https://ffmpeg.org/
    This preview build does not bundle ffmpeg.

Your videos are read in place from wherever you point "Add folder" -
nothing is uploaded or copied anywhere. All data (which videos you've
added, your cut/keep decisions, tags) is stored locally in
%USERPROFILE%\.snip-snap\snip-snap.db
