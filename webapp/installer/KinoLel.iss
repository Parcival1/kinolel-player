; KinoLel für Windows (Web-App, Electron) – Installer (Inno Setup 6)
; Gleiche AppId wie die bisherige Qt-App: ein Update (auch über deren Auto-Update, das das Setup mit /SILENT startet)
; ersetzt die alte Installation an derselben Stelle. Danach gibt es nur eine KinoLel-Installation.
; Aufruf: ISCC /DVersion=0.3.0 /DQuelle=<ordner mit KinoLel.exe> /DAusgabe=<ordner> KinoLel.iss

#define MyAppName "KinoLel"
#define MyAppPublisher "Lel"
#define MyAppURL "https://kinolel.de"
#define MyAppExeName "KinoLel.exe"
#define MyAppGUID "{{35069221-331e-4793-bed0-a842d0e01949}"
#define MyAppDescription "Filme und Serien von KinoLel"
#define MyAppUserModelId "de.kinolel.windows"
#define MitDeutsch FileExists(AddBackslash(CompilerPath) + "Languages\German.isl")
#define MitUngarisch FileExists(AddBackslash(CompilerPath) + "Languages\Hungarian.isl")

[Setup]
AppId={#MyAppGUID}
AppName={#MyAppName}
AppVersion={#Version}
AppVerName={#MyAppName} {#Version}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppComments={#MyAppDescription}
VersionInfoVersion={#Version}.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#Version}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Lel
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
MinVersion=10.0.18362
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#Ausgabe}
OutputBaseFilename={#MyAppName}-Setup-{#Version}-x64
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=wizard-image.png
WizardSmallImageFile=wizard-small-image.png
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto

[Languages]
#if MitDeutsch
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
#endif
#if MitUngarisch
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
#if MitDeutsch
german.TvModus=%1 (TV-Modus)
german.TvModusInfo=%1 im Vollbild mit TV-Oberfläche (Fernbedienung/Gamepad)
german.Starten=%1 starten
german.DatenLoeschen=Sollen auch die Einstellungen und die Anmeldung von %1 auf diesem PC gelöscht werden?
#endif
#if MitUngarisch
hungarian.TvModus=%1 (TV mód)
hungarian.TvModusInfo=%1 teljes képernyőn, TV-felülettel (távirányító/kontroller)
hungarian.Starten=%1 indítása
hungarian.DatenLoeschen=Törölni szeretnéd a(z) %1 beállításait és bejelentkezését is erről a gépről?
#endif
english.TvModus=%1 (TV mode)
english.TvModusInfo=%1 fullscreen with TV interface (remote/gamepad)
english.Starten=Launch %1
english.DatenLoeschen=Do you also want to remove the %1 settings and login on this PC?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "tvicon"; Description: "{cm:TvModus,{#MyAppName}}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Quelle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"
Name: "{autoprograms}\{cm:TvModus,{#MyAppName}}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tv"; Comment: "{cm:TvModusInfo,{#MyAppName}}"; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "{#MyAppUserModelId}"
Name: "{autodesktop}\{cm:TvModus,{#MyAppName}}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tv"; Comment: "{cm:TvModusInfo,{#MyAppName}}"; WorkingDir: "{app}"; Tasks: tvicon; AppUserModelID: "{#MyAppUserModelId}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:Starten,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; Auto-Update aus der App (/SILENT): danach KinoLel wieder starten
Filename: "{app}\{#MyAppExeName}"; Flags: nowait; Check: WizardSilent

[Code]
var
  RemoveUserData: Boolean;

// Vor dem Kopieren: alte Programmdateien im Installationsordner entfernen (bisherige Qt-App bzw. ältere Version),
// damit nichts Veraltetes liegen bleibt. Nur Programmdateien – Einstellungen/Anmeldung liegen unter %LOCALAPPDATA%.
procedure AlteProgrammdateienEntfernen;
var
  Rec: TFindRec;
  Ordner: String;
begin
  Ordner := ExpandConstant('{app}');
  if not (FileExists(Ordner + '\{#MyAppExeName}') or FileExists(Ordner + '\Qt6Core.dll')) then Exit;
  if FindFirst(Ordner + '\*', Rec) then
  try
    repeat
      if (Rec.Name <> '.') and (Rec.Name <> '..') and (Pos('unins', Lowercase(Rec.Name)) <> 1) then
      begin
        if (Rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          DelTree(Ordner + '\' + Rec.Name, True, True, True)
        else
          DeleteFile(Ordner + '\' + Rec.Name);
      end;
    until not FindNext(Rec);
  finally
    FindClose(Rec);
  end;
  Log('Alte Programmdateien entfernt: ' + Ordner);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then AlteProgrammdateienEntfernen;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  CacheDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#MyAppName}');
    CacheDir := ExpandConstant('{localappdata}\cache\{#MyAppName}');
    if (DirExists(DataDir) or DirExists(CacheDir)) and not UninstallSilent then
      RemoveUserData := MsgBox(FmtMessage(CustomMessage('DatenLoeschen'), ['{#MyAppName}']), mbConfirmation, MB_YESNO) = IDYES;
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    if RemoveUserData then
    begin
      DelTree(ExpandConstant('{localappdata}\{#MyAppName}'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\cache\{#MyAppName}'), True, True, True);
    end;
  end;
end;
