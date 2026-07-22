; ============================================================================
; Wain Inno Setup Script (v2.24.0)
; ============================================================================
; Build: ISCC installer.iss  (or via build_installer.bat, which passes the
; version from wain/config.py as /DMyAppVersion=x.y.z)
; Requires: Inno Setup 6 — https://jrsoftware.org/isinfo.php
; Input:    dist\Wain\  (produced by `pyinstaller wain.spec`)
; Output:   dist\installer\Wain-Setup-<version>.exe
;
; https://github.com/sbuff25/RenderManager
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "2.24.0"
#endif
; Build output directory (passed by build_installer.bat as /DBuildDir=...)
#ifndef BuildDir
  #define BuildDir "dist"
#endif

#define MyAppName "Wain"
#define MyAppPublisher "Spencer"
#define MyAppURL "https://github.com/sbuff25/RenderManager"
#define MyAppExeName "Wain.exe"

[Setup]
AppId={{8B1F4E62-9C3A-4D5E-B7F0-WAIN20200001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir={#BuildDir}\installer
OutputBaseFilename=Wain-Setup-{#MyAppVersion}
SetupIconFile=assets\wain_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "workershortcut"; Description: "Create a ""Wain Worker"" shortcut (render node mode)"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "firewall"; Description: "Add a Windows Firewall rule for network rendering (port 8080)"; GroupDescription: "Network rendering:"; Flags: unchecked

[Files]
Source: "{#BuildDir}\Wain\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "portable_install.bat,portable_uninstall.bat"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName} Worker (render node)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--worker"; Tasks: workershortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Optional firewall rule so workers can reach the server (inbound 8080)
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Wain Render Server"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Wain Render Server"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"

[UninstallDelete]
; Note: user data (config, job DB, logs) in %APPDATA%\Wain is intentionally
; NOT deleted — render history and settings survive reinstalls.
Type: filesandordirs; Name: "{app}"
