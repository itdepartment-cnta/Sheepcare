; ============================================================================
; SheepCare — Instalador (Inno Setup 6)  |  Versión sin Docker
; ============================================================================

#define AppName      "SheepCare"
#ifndef AppVersion
  #define AppVersion "1.0"
#endif
#define AppPublisher "CNTA"
#define AppURL       "http://localhost:48000"

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
; Todos los servicios se arrancan desacoplados del lanzador y siguen vivos al cerrar su ventana:
; se paran antes de borrar sus ficheros. PostgreSQL el ultimo, y de forma limpia.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM SheepCare.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopLauncher"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-backend.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopBackend"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-weather.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopWeather"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-reporting.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopReporting"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-calendar.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopCalendar"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM sheepcare-gatekeeper.exe"; Flags: runhidden waituntilterminated; RunOnceId: "StopGatekeeper"
; mongod: solo el NUESTRO (el de {app}). Por nombre se llevaria por delante el MongoDB propio del equipo,
; por eso el lanzador usa el puerto 27018. Las llaves se duplican: en este fichero {{ abre una constante.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'mongod.exe' -and $_.ExecutablePath -like '{app}\mongodb\*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"""; Flags: runhidden waituntilterminated; RunOnceId: "StopMongo"
Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters: "stop -D ""{userappdata}\SheepCare\pgdata"" -m fast"; Flags: runhidden waituntilterminated; RunOnceId: "StopPostgres"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
{ Los servicios de SheepCare se arrancan desacoplados del lanzador y siguen vivos tras cerrar su
  ventana. Al ACTUALIZAR hay que pararlos antes de copiar ficheros: si no, Windows no deja sustituir
  sus ejecutables y, peor, el lanzador ve el puerto 48000 ocupado ("SheepCare ya esta activo") y
  reutiliza el backend VIEJO que sigue en memoria, sin las migraciones ni la sincronizacion nuevas. }

procedure PararProceso(const Imagen: String);
var
  Codigo: Integer;
begin
  { taskkill devuelve 128 si no hay ningun proceso con ese nombre: no es un error }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM ' + Imagen, '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

procedure PararMongoDeSheepCare;
var
  Codigo: Integer;
begin
  { Solo el mongod de la carpeta de instalacion: el equipo puede tener su propio MongoDB, que no se toca }
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq ''mongod.exe'' -and $_.ExecutablePath -like ''' +
    ExpandConstant('{app}') + '\mongodb\*'' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
    '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

procedure PararServiciosDeSheepCare;
var
  Codigo: Integer;
  PgCtl: String;
begin
  PararProceso('SheepCare.exe');
  PararProceso('sheepcare-backend.exe');
  PararProceso('sheepcare-reporting.exe');
  PararProceso('sheepcare-weather.exe');
  PararProceso('sheepcare-calendar.exe');
  PararProceso('sheepcare-gatekeeper.exe');
  PararMongoDeSheepCare;
  { PostgreSQL se para limpiamente: guarda los datos de GateKeeper y de Farm Calendar }
  PgCtl := ExpandConstant('{app}\pgsql\bin\pg_ctl.exe');
  if FileExists(PgCtl) then
    Exec(PgCtl, ExpandConstant('stop -D "{userappdata}\SheepCare\pgdata" -m fast'), '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  { Un respiro para que Windows libere los ficheros }
  Sleep(1500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  PararServiciosDeSheepCare;
  Result := '';
end;
