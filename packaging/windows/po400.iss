; Inno Setup script for the po400 Windows installer.
;
; Installs %LOCALAPPDATA%\Programs\po400\po400.exe with a Start Menu group and
; an Explorer context-menu entry, both under HKCU, so the installer needs no
; administrator rights (PACKAGING.md "Windows"). No PATH entry is written.
;
; DESIGN DECISION (psytrap, 2026-10-15) -- do not "improve" this back:
;   The Start Menu entry runs po400.exe DIRECTLY. Launched with no arguments the
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
;   ISCC /DAppVersion=0.1.1 packaging\windows\po400.iss
; The default below is only a fallback for a hand-run build.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#ifndef SourceExe
  #define SourceExe "..\..\dist\po400.exe"
#endif

[Setup]
AppId={{1C4AFF42-942E-45D2-ACF1-908840BCC434}
AppName=PO-400 Oximeter
AppVersion={#AppVersion}
AppVerName=PO-400 Oximeter {#AppVersion}
AppPublisher=psytrap
DefaultDirName={localappdata}\Programs\po400
DefaultGroupName=PO-400
UninstallDisplayName=PO-400 Oximeter
OutputBaseFilename=po400-setup
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
; the user's recordings when po400 is uninstalled.
Name: "{userdocs}\PO-400"; Flags: uninsneveruninstall

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PO-400 Oximeter"; Filename: "{app}\po400.exe"; WorkingDir: "{userdocs}\PO-400"
Name: "{group}\Uninstall PO-400"; Filename: "{uninstallexe}"

[Tasks]
Name: "contextmenu"; Description: "Add ""Open PO-400 Console here"" to the Explorer right-click menu"; GroupDescription: "Integration:"

[Registry]
; Explorer context menu, both on a folder and on the folder background.
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\po400"; ValueType: string; ValueName: ""; \
    ValueData: "Open PO-400 here"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\po400"; ValueType: string; ValueName: "Icon"; \
    ValueData: "{app}\po400.exe,0"; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\shell\po400\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\po400.exe"""; Tasks: contextmenu

Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\po400"; ValueType: string; ValueName: ""; \
    ValueData: "Open PO-400 here"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\po400"; ValueType: string; ValueName: "Icon"; \
    ValueData: "{app}\po400.exe,0"; Tasks: contextmenu
Root: HKCU; Subkey: "SOFTWARE\Classes\Directory\Background\shell\po400\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\po400.exe"""; Tasks: contextmenu
