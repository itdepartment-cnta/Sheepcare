; ============================================================================
; SheepCare — Instalador (Inno Setup 6)  |  Versión sin Docker
; ============================================================================

#define AppName      "SheepCare"
#ifndef AppVersion
  #define AppVersion "1.0"
#endif
#define AppPublisher "CNTA"
#define AppURL       "http://localhost:8000"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=SheepCare-Setup-{#AppVersion}
OutputDir=dist
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=assets\sheepcare.ico
UninstallDisplayIcon={app}\SheepCare.exe
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=SheepCare - Gestion de ovino

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Launcher (exe unico)
Source: "dist\SheepCare.exe"; DestDir: "{app}"; Flags: ignoreversion

; Backend (carpeta con dependencias Python)
Source: "dist\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs

; FarmCalendar (carpeta con dependencias Python + Django)
Source: "dist\calendar\*"; DestDir: "{app}\calendar"; Flags: ignoreversion recursesubdirs

; GateKeeper (carpeta con dependencias Python + Django)
Source: "dist\gatekeeper\*"; DestDir: "{app}\gatekeeper"; Flags: ignoreversion recursesubdirs

; Weather (OpenAgri Weather Service: tiempo y THI)
Source: "dist\weather\*"; DestDir: "{app}\weather"; Flags: ignoreversion recursesubdirs

; Reporting (OpenAgri Reporting Service: informes PDF)
Source: "dist\reporting\*"; DestDir: "{app}\reporting"; Flags: ignoreversion recursesubdirs

; PostgreSQL portable
Source: "pgsql\*"; DestDir: "{app}\pgsql"; Flags: ignoreversion recursesubdirs

; MongoDB portable (solo mongod.exe y sus licencias): la cache de Weather
Source: "mongodb\*"; DestDir: "{app}\mongodb"; Flags: ignoreversion recursesubdirs

; Icono
Source: "assets\sheepcare.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SheepCare.exe"; IconFilename: "{app}\assets\sheepcare.ico"; Comment: "Iniciar SheepCare"
Name: "{group}\{#AppName}"; Filename: "{app}\SheepCare.exe"; IconFilename: "{app}\assets\sheepcare.ico"; Comment: "Iniciar SheepCare"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\SheepCare.exe"; Description: "Iniciar SheepCare ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Los servicios nuevos se paran antes de borrar sus ficheros (se arrancan desacoplados)
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-weather.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopWeather"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-reporting.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopReporting"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM mongod.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopMongo"
Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters: "stop -D ""{userappdata}\SheepCare\pgdata"" -m fast"; Flags: runhidden waituntilterminated; RunOnceId: "StopPostgres"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
