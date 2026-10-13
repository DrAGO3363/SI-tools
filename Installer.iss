
#define MyAppName "SI tools"
#define MyAppVersion "1.0.0"
#define MyAppExeName "SEO Universal Amir Edition.exe"
#define MyAppSourceDir "SEO Universal Amir Edition"

[Setup]
AppId={{CDE529F3-A4AC-4E8B-8E1F-09BEBBF12AF4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Amir.exe

DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=installer-output
OutputBaseFilename=SI-tools-Setup

SetupIconFile=app.ico
UninstallDisplayIcon={app}\app.ico

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SI tools"; Flags: nowait postinstall skipifsilent
