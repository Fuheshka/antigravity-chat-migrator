; Inno Setup 6 — Antigravity Chat Migrator Windows Installer
; Publisher : Daniil K. (Fuheshka)  https://github.com/Fuheshka/antigravity-chat-migrator
; Requires  : Inno Setup 6.3+ (https://jrsoftware.org/isinfo.php)
;
; Build:
;   iscc packaging\windows\setup.iss
;
; Output: dist\windows\Antigravity-Chat-Migrator-Windows-x64-Setup.exe

#define AppName      "Antigravity Chat Migrator"
#define AppVersion   "0.1.0"
#define AppPublisher "Daniil K. (Fuheshka)"
#define AppURL       "https://github.com/Fuheshka/antigravity-chat-migrator"
#define AppId        "{{A8C3F2D1-4B7E-4F9A-8C2D-1E6B5A3F9D2E}"
#define AppExeName   "Antigravity Chat Migrator.exe"
#define AppCLIName   "agy-migrator.exe"

; Paths relative to this .iss file (packaging/windows/)
#define SrcDir       "..\..\dist\windows"
#define AssetsDir    "..\assets"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; No UAC prompt — installs to %LOCALAPPDATA%\Programs\<AppName>
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; x64 only
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Output
OutputDir=..\..\dist\windows
OutputBaseFilename=Antigravity-Chat-Migrator-Windows-x64-Setup
SetupIconFile={#AssetsDir}\AppIcon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Visual
WizardStyle=modern
WizardResizable=no
ShowLanguageDialog=auto

; Misc
DisableWelcomePage=no
DisableReadyPage=no
AllowNoIcons=yes
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=yes

; Uninstall info
UninstallDisplayName={#AppName}
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
; English
english.DesktopIconDesc=Create a &desktop shortcut
english.AddToPathDesc=Add CLI utility agy-migrator to system &PATH (current user)
english.AddToPathNote=Required for running 'agy-migrator' from any terminal without the full path.
english.ViewReadme=View README.txt

; Russian
russian.DesktopIconDesc=Создать ярлык на &рабочем столе
russian.AddToPathDesc=Добавить CLI-утилиту agy-migrator в системный &PATH (текущий пользователь)
russian.AddToPathNote=Позволяет запускать 'agy-migrator' из любого терминала без указания полного пути.
russian.ViewReadme=Открыть README.txt

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIconDesc}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "addtopath";   Description: "{cm:AddToPathDesc}";   GroupDescription: "{cm:AdditionalIcons}"

[Files]
; GUI binary
Source: "{#SrcDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; CLI binary
Source: "{#SrcDir}\{#AppCLIName}"; DestDir: "{app}"; Flags: ignoreversion

; Helper batch launcher
Source: "run_fix.bat"; DestDir: "{app}"; Flags: ignoreversion

; Documentation
Source: "README_WINDOWS.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion isreadme

; License
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
; Start Menu shortcut (GUI)
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Comment: "Antigravity Chat Migrator — fix Outside of Project chats"

; Uninstall entry in Start Menu
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional, checked by default)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Add app install dir to user PATH (HKCU) when task is selected
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: addtopath; Flags: preservestringtype uninsdeletevalue

[Run]
; Offer to open README after install
Filename: "{app}\README.txt"; Description: "{cm:ViewReadme}"; Flags: postinstall shellexec skipifsilent unchecked

; Offer to launch GUI after install
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Remove log/cache files left by the app
Type: filesandordirs; Name: "{localappdata}\{#AppName}\cache"
Type: filesandordirs; Name: "{localappdata}\{#AppName}\logs"
Type: dirifempty;     Name: "{localappdata}\{#AppName}"

[Code]
// ---------------------------------------------------------------------------
// NeedsAddPath: returns True when {app} is NOT already in the user PATH.
// ---------------------------------------------------------------------------
function NeedsAddPath(AppPath: string): Boolean;
var
  UserPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', UserPath) then
  begin
    Result := True;
    Exit;
  end;
  // Case-insensitive substring check
  Result := Pos(';' + Uppercase(AppPath) + ';', ';' + Uppercase(UserPath) + ';') = 0;
end;

// ---------------------------------------------------------------------------
// CurUninstallStepChanged: clean up PATH entry on uninstall when it was added.
// ---------------------------------------------------------------------------
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserPath, AppPath, NewPath: string;
  P: Integer;
begin
  if CurUninstallStep <> usPostUninstall then Exit;

  AppPath := ExpandConstant('{app}');
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', UserPath) then Exit;

  P := Pos(';' + AppPath, UserPath);
  if P > 0 then
  begin
    NewPath := Copy(UserPath, 1, P - 1) + Copy(UserPath, P + Length(';' + AppPath), MaxInt);
    RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath);
  end;
end;
