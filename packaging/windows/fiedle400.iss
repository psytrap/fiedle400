; Inno Setup script for the fiedle400 Windows installer.
;
; Installs %LOCALAPPDATA%\Programs\fiedle400\fiedle400.exe with a Start Menu group and
; an Explorer context-menu entry, both under HKCU, so the installer needs no
; administrator rights (PACKAGING.md "Windows"). No PATH entry is written.
;
; DESIGN DECISION (psytrap, 2026-10-15) -- do not "improve" this back:
;   The Start Menu entry runs fiedle400.exe DIRECTLY. Launched with no arguments the
;   binary starts its interactive wizard (cli.py: `handler = args.func if
;   args.command else run_interactive_wizard`), so clicking the icon just works.
;
;   Therefore this installer deliberately does NOT:
;     * write a PATH entry (no registry Environment key, no session PATH),
;     * ship a cmd/doskey launcher shim,
;     * open a command prompt for the user to type into.
;
;   The user never needs a command line. Anyone tempted to add a PATH entry or a
;   console shim "for convenience" should change the UX decision first, not the
;   installer.
;
; The version is passed in by CI so it cannot drift from the Python manifests:
;   ISCC /DAppVersion=0.1.1 packaging\windows\fiedle400.iss
; The default below is only a fallback for a hand-run build.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#ifndef SourceExe
  #define SourceExe "..\..\dist\fiedle400.exe"
#endif

; Synthetic (no real device data) demo recording, T-055; regenerate with
; scripts/make_demo_recording.py if it ever needs to change.
#ifndef DemoSpo2
  #define DemoSpo2 "demo.SpO2"
#endif

; RENAME (po400 -> fiedle400): the AppId is unchanged on purpose, so this
; installer upgrades an existing po400 install instead of installing beside it.
; UsePreviousAppDir=no moves it to the new folder; [InstallDelete] removes the
; old folder and the [Registry] deletekey lines remove the old context-menu keys.
; The recordings folder was kept as "PO-400" at first (the device's name), but
; psytrap later asked for the app's own name everywhere (T-064) -- the group
; folder, uninstall shortcut, and Explorer context-menu text included. The
; recordings folder name must stay in lock-step with fiedle400/config.py's
; default_workdir(), which hardcodes the same path for the same reason (its
; docstring explains why).

[Setup]
AppId={{1C4AFF42-942E-45D2-ACF1-908840BCC434}
AppName=fiedle400
AppVersion={#AppVersion}
AppVerName=fiedle400 {#AppVersion}
AppPublisher=psytrap
DefaultDirName={localappdata}\Programs\fiedle400
UsePreviousAppDir=no
DefaultGroupName=fiedle400
UninstallDisplayName=fiedle400
OutputBaseFilename=fiedle400-setup
OutputDir=..\..\installer
Compression=lzma2
SolidCompression=yes
; User-local install: never prompt for UAC.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
DisableDirPage=no
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Dirs]
; Default landing folder for the Start Menu shortcut. uninsneveruninstall keeps
; the user's recordings when fiedle400 is uninstalled. Must match
; fiedle400/config.py's default_workdir() (T-064).
Name: "{userdocs}\fiedle400"; Flags: uninsneveruninstall

[InstallDelete]
; Leftovers of a po400 install (pre-rename). Only the old program folder; the
; recordings live in {userdocs}\fiedle400 and are never touched.
Type: filesandordirs; Name: "{localappdata}\Programs\po400"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DemoSpo2}"; DestDir: "{userdocs}\fiedle400"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\fiedle400"; Filename: "{app}\fiedle400.exe"; WorkingDir: "{userdocs}\fiedle400"
Name: "{group}\View Demo Recording"; Filename: "{app}\fiedle400.exe"; \
    Parameters: "view ""{userdocs}\fiedle400\demo.SpO2"""; WorkingDir: "{userdocs}\fiedle400"
Name: "{group}\Uninstall fiedle400"; Filename: "{uninstallexe}"

[Tasks]
Name: "contextmenu"; Description: "Add ""Open fiedle400 Console here"" to the Explorer right-click menu"; GroupDescription: "Integration:"

[Registry]
; Remove the pre-rename context-menu keys, whether or not the task is chosen now.
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\po400"; ValueType: none; Flags: deletekey
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\po400"; ValueType: none; Flags: deletekey

; Explorer context menu, both on a folder and on the folder background.
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\fiedle400"; ValueType: string; ValueName: ""; \
    ValueData: "Open fiedle400 here"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\fiedle400"; ValueType: string; ValueName: "Icon"; \
    ValueData: "{app}\fiedle400.exe,0"; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\fiedle400\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\fiedle400.exe"""; Tasks: contextmenu

Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\fiedle400"; ValueType: string; ValueName: ""; \
    ValueData: "Open fiedle400 here"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\fiedle400"; ValueType: string; ValueName: "Icon"; \
    ValueData: "{app}\fiedle400.exe,0"; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\fiedle400\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\fiedle400.exe"""; Tasks: contextmenu
