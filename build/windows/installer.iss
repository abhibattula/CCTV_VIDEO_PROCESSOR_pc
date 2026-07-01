; Inno Setup script for CCTV Video Processor (Windows x64)
; Builds a single-file .exe installer that wraps the PyInstaller --onedir output.
;
; IMPORTANT (FR-023 / FR-024):
;   This installer MUST NOT touch ~/.cctv_processor/.
;   App data (jobs, models, sentinel) is created by the app itself on first run.
;   Uninstalling MUST NOT delete user data in ~/.cctv_processor/.
;
; Usage:
;   iscc /DAppVersion=1.0.0 build\windows\installer.iss
;
; Prerequisite:  PyInstaller onedir output at dist\CCTV-Video-Processor\

#ifndef AppVersion
  #define AppVersion "dev"
#endif

#define AppName      "CCTV Video Processor"
#define AppPublisher "CCTV Video Processor Project"
#define AppExeName   "CCTV-Video-Processor.exe"
#define DistDir      "..\..\dist\CCTV-Video-Processor"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Do NOT touch user data directories
; (UninstallDisplayIcon references only the install dir, never APPDATA)
OutputDir=..\..\dist
OutputBaseFilename=CCTV-Video-Processor-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.17763
DisableProgramGroupPage=yes
; No changes to Windows Defender or shell extensions needed

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copy entire PyInstaller onedir output
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only remove files the installer put there (install dir contents)
; User data in %USERPROFILE%\.cctv_processor is explicitly excluded
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Intentionally empty: do NOT touch ~/.cctv_processor or APPDATA
  // User videos, jobs, and model downloads remain intact after uninstall.
end;
