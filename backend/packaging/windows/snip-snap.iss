#ifndef AppVersion
  #error AppVersion preprocessor define is required (example: /DAppVersion=1.2.3)
#endif

[Setup]
AppId={{E1775A2D-265D-4C33-8278-F55F8D8D5336}
AppName=snip-snap
AppVersion={#AppVersion}
AppPublisher=Noah Wright
DefaultDirName={localappdata}\Programs\snip-snap
DefaultGroupName=snip-snap
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\snip-snap.exe
OutputDir=output
OutputBaseFilename=snip-snap-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\snip-snap.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\snip-snap"; Filename: "{app}\snip-snap.exe"
Name: "{autodesktop}\snip-snap"; Filename: "{app}\snip-snap.exe"

[Run]
Filename: "{app}\snip-snap.exe"; Description: "Launch snip-snap"; Flags: nowait postinstall skipifsilent

