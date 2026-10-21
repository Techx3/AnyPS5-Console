#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F4E2C51-8B0B-4C7E-9F3A-5A1D7E0C2B91}
AppName=AnyPS5 Console
AppVersion={#AppVersion}
AppPublisher=Larimar Studios
DefaultDirName={localappdata}\Programs\AnyPS5 Console
DefaultGroupName=AnyPS5 Console
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=AnyPS5Console-Setup-{#AppVersion}
SetupIconFile=..\src\assets\anyps5.ico
UninstallDisplayIcon={app}\AnyPS5Console.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.BuildTools=Download build tools (Git + MinGW, about 350 MB). Only needed for the Repository version and forks.
spanish.BuildTools=Descargar herramientas de compilación (Git + MinGW, unos 350 MB). Solo para la versión Repositorio y forks.
french.BuildTools=Télécharger les outils de compilation (Git + MinGW, environ 350 Mo). Uniquement pour la version Dépôt et les forks.
english.Downloading=Downloading Git and MinGW...
spanish.Downloading=Descargando Git y MinGW...
french.Downloading=Téléchargement de Git et MinGW...

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "buildtools"; Description: "{cm:BuildTools}"; Flags: unchecked

[Files]
Source: "..\dist\AnyPS5Console\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AnyPS5 Console"; Filename: "{app}\AnyPS5Console.exe"
Name: "{group}\{cm:UninstallProgram,AnyPS5 Console}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AnyPS5 Console"; Filename: "{app}\AnyPS5Console.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AnyPS5Console.exe"; Parameters: "--install-tools"; StatusMsg: "{cm:Downloading}"; Flags: runhidden waituntilterminated; Tasks: buildtools
Filename: "{app}\AnyPS5Console.exe"; Description: "{cm:LaunchProgram,AnyPS5 Console}"; Flags: nowait postinstall skipifsilent
