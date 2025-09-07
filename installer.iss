; Inno Setup script for timerMQTT
#define MyAppName "timerMQTT"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "timerMQTT"
#define MyAppExeName "timerMQTT.exe"

[Setup]
AppId={{A3A6F3C5-6B32-4D0D-8C0F-FA74B74B7C8E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=timerMQTT-Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=
WizardStyle=modern

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "dist\timerMQTT.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
