; Inno Setup script for the RXTERM Windows installer.
;   iscc /DAppVersion=1.0.0 packaging\rxterm.iss      (after: pyinstaller packaging\rxterm.spec)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B2E0F3C-8F4A-4C1B-9E57-RXTERM000001}
AppName=RXTERM
AppVersion={#AppVersion}
AppVerName=RXTERM {#AppVersion}
AppPublisher=RXTERM
AppComments=Pharma & biotech trading terminal
DefaultDirName={localappdata}\Programs\RXTERM
DefaultGroupName=RXTERM
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=RXTERM-Setup
SetupIconFile=..\assets\rxterm.ico
UninstallDisplayIcon={app}\RXTERM.exe
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\RXTERM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\RXTERM"; Filename: "{app}\RXTERM.exe"; WorkingDir: "{app}"; Comment: "Pharma & biotech trading terminal"
Name: "{userprograms}\RXTERM User Guide"; Filename: "{app}\_internal\docs\USER_GUIDE.md"
Name: "{userdesktop}\RXTERM"; Filename: "{app}\RXTERM.exe"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Pharma & biotech trading terminal"

[Run]
Filename: "{app}\RXTERM.exe"; Description: "Open RXTERM now"; Flags: nowait postinstall skipifsilent
