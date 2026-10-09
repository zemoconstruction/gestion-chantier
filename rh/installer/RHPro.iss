; Script Inno Setup : fabrique RHPro-Setup.exe (installateur avec raccourcis)
#define AppName "RH Pro"
#define AppVersion "1.0"

[Setup]
AppId={{6F2B8E3A-4C1D-4E7A-9B55-3A7C10D2E001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=RH Pro
DefaultDirName={autopf}\RH Pro
DefaultGroupName=RH Pro
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=RHPro-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
DisableProgramGroupPage=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: checkedonce

[Files]
Source: "..\dist\RHPro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RH Pro"; Filename: "{app}\RHPro.exe"
Name: "{autodesktop}\RH Pro"; Filename: "{app}\RHPro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RHPro.exe"; Description: "Lancer RH Pro maintenant"; Flags: nowait postinstall skipifsilent
; Les données (base, documents) restent dans %LOCALAPPDATA%\RHPro\data et sont conservées à la désinstallation.
