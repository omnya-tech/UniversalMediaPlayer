; ملف إعدادات Inno Setup لبناء مثبّت (Installer) لبرنامج مشغل الوسائط الشامل.
;
; المتطلبات:
; 1) يجب بناء dist\Universal Media Player\Universal Media Player.exe مسبقًا باستخدام PyInstaller.
; 2) تنزيل وتثبيت Inno Setup (مجاني) من:
;    https://jrsoftware.org/isdl.php
;
; طريقة البناء:
; - افتحي هذا الملف بواسطة Inno Setup Compiler ثم اختاري Build > Compile.
;
; سيكون الناتج في installer_output\Universal_Media_Player_Setup_1.5.0.exe

#define MyAppName "Universal Media Player"
#define MyAppVersion "1.5.0"
#define MyAppExeName "Universal Media Player.exe"
#define MyAppPublisher "Omnya Technology"

[Setup]
AppId={{0D11ED1A-113D-4575-B7B0-E8F54093FE0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\Universal Media Player
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=resources\omnya_icon.ico
OutputDir=installer_output
OutputBaseFilename=Universal_Media_Player_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=classic
PrivilegesRequired=admin
MinVersion=10.0
; إظهار نافذة اختيار اللغة عند بدء التثبيت
ShowLanguageDialog=yes
LanguageDetectionMethod=none

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
; =========================================================
; --- قاموس مفاتيح الترجمة المعتمد للبرنامج بأكمله ---
; =========================================================
arabic.AppName=مشغل الوسائط الشامل
arabic.AppDesc=مشغل وسائط متاح وسهل الاستخدام لقارئات الشاشة
arabic.MenuPlay=تشغيل بواسطة مشغل الوسائط الشامل
arabic.MenuConvert=تحويل بواسطة مشغل الوسائط الشامل
arabic.MenuConvertDir=تحويل المجلد بواسطة مشغل الوسائط الشامل
arabic.MediaFileDesc=ملف وسائط (مشغل الوسائط الشامل)
arabic.WarmingUp=جاري تجهيز محرك التشغيل لأول استخدام...

english.AppName=Universal Media Player
english.AppDesc=Accessible and easy-to-use media player for screen readers
english.MenuPlay=Play with Universal Media Player
english.MenuConvert=Convert with Universal Media Player
english.MenuConvertDir=Convert folder with Universal Media Player
english.MediaFileDesc=Universal Media Player Media File
english.WarmingUp=Preparing the playback engine for first use...
; =========================================================

[Files]
Source: "dist\Universal Media Player\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; الرخصة وTHIRD-PARTY.md ومجلد licenses داخل dist نفسه (يضعها omnya_player.spec
; بعد البناء)، فيصلان مع السطر السابق ومع النسخة المحمولة كذلك

[Icons]
; ربط أسماء الاختصارات (على سطح المكتب وقائمة إبدأ) بمفتاح الترجمة cm:AppName
Name: "{group}\{cm:AppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{cm:AppName}"; Filename: "{app}\{#MyAppExeName}"

[UninstallDelete]
; ---------------------------------------------------------------------
; --- مسح جذري لكل متعلقات البرنامج عند الإزالة (Clean Uninstall) ---
; ---------------------------------------------------------------------
; 1. مسح مجلد الإعدادات (AppData) الخاص بالبرنامج بما يحتويه من ملفات json وسجلات
;    البرنامج من 1.4.0 بيحفظ في Omnya (شوف core/logging_setup.py)، وOmniaPlayer
;    هو الاسم القديم لو لسه ما اتنقلش
Type: filesandordirs; Name: "{userappdata}\Omnya"
Type: filesandordirs; Name: "{userappdata}\OmniaPlayer"
; 2. مسح مجلد تثبيت البرنامج (Program Files) بالكامل في حال تبقت فيه ملفات تم إنشاؤها بعد التثبيت
Type: filesandordirs; Name: "{app}"

[Code]
{ قائمة الامتدادات المسجّلة، لازم تفضل مطابقة لقسم [Registry] تحت }
function GetExtensionList(): String;
begin
  Result := '.mp3|.wav|.flac|.m4a|.aac|.ogg|.wma|.oga|.opus|.aiff|.aif|.ape|.alac|.amr|.caf|.au|.mid|.midi|.ac3|.dts|.mka|.weba|.tta|.wv|.mpc|.spx|.dsf|.dff|.voc|.gsm|.mpa|.tsa|.mus|.mp4|.mkv|.avi|.mov|.wmv|.flv|.webm|.mpg|.mpeg|.mpe|.mas|.npa|.m4v|.3gp|.3g2|.ts|.mts|.m2ts|.vob|.ogv|.rm|.rmvb|.asf|.divx|.f4v|.mxf|.qt|.wtv|.ogm|.y4m|.nut|';
end;

function GetSettingsFilePath(): String;
begin
  Result := ExpandConstant('{userappdata}') + '\Omnya\settings.json';
end;

procedure WriteInitialLanguageSetting();
var
  SettingsPath, SettingsDir, LangCode: String;
begin
  SettingsPath := GetSettingsFilePath();
  if FileExists(SettingsPath) then
    exit;

  if ActiveLanguage() = 'arabic' then
    LangCode := 'ar'
  else
    LangCode := 'en';

  SettingsDir := ExtractFileDir(SettingsPath);
  if not DirExists(SettingsDir) then
    ForceDirectories(SettingsDir);

  SaveStringToFile(SettingsPath, '{"language": "' + LangCode + '"}', False);
end;

procedure CleanOldRegistryGhosts();
var
  ExtString, Ext: String;
  P: Integer;
begin
  { تنظيف صارم لأي أشباح قديمة قبل تسجيل المفاتيح الجديدة }
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\Directory\shell\OmnyaConvertDir');
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\Directory\shell\UMPConvertDir');
  
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\Omnya.MediaFile');
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\UMP.MediaFile');

  ExtString := GetExtensionList();
  
  while Length(ExtString) > 0 do
  begin
    P := Pos('|', ExtString);
    if P > 0 then
    begin
      Ext := Copy(ExtString, 1, P - 1);
      Delete(ExtString, 1, P);
      
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\SystemFileAssociations\' + Ext + '\shell\OmnyaPlay');
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\SystemFileAssociations\' + Ext + '\shell\OmnyaConvert');
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\SystemFileAssociations\' + Ext + '\shell\UMPPlay');
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\SystemFileAssociations\' + Ext + '\shell\UMPConvert');
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    CleanOldRegistryGhosts();
  end;
  
  if CurStep = ssPostInstall then
  begin
    WriteInitialLanguageSetting();
  end;
end;

{ أسماء البرامج اللي ويندوز بيحفظها في MuiCache بمسار الـ exe:
  بعد الإزالة كان الاسم بيفضل ظاهر في "فتح باستخدام" }
procedure CleanMuiCache();
var
  Names: TArrayOfString;
  I: Integer;
  ExePath, Key: String;
begin
  Key := 'Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache';
  ExePath := LowerCase(ExpandConstant('{app}\{#MyAppExeName}'));
  if RegGetValueNames(HKEY_CURRENT_USER, Key, Names) then
    for I := 0 to GetArrayLength(Names) - 1 do
      if Pos(ExePath, LowerCase(Names[I])) = 1 then
        RegDeleteValue(HKEY_CURRENT_USER, Key, Names[I]);
end;

{ المفاتيح اللي ويندوز بيعملها لوحده لما المستخدم يفتح ملف بالبرنامج.
  UserChoice بيتمسح بس لو كان مختار برنامجنا، علشان اختيارات المستخدم
  لبرامج تانية ما تتلمسش }
procedure CleanWindowsGeneratedKeys(Ext: String);
var
  Names: TArrayOfString;
  I: Integer;
  Base, Value: String;
begin
  Base := 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\' + Ext;
  RegDeleteValue(HKEY_CURRENT_USER, Base + '\OpenWithProgids', 'UMP.MediaFile');
  if RegGetValueNames(HKEY_CURRENT_USER, Base + '\OpenWithList', Names) then
    for I := 0 to GetArrayLength(Names) - 1 do
      if RegQueryStringValue(HKEY_CURRENT_USER, Base + '\OpenWithList', Names[I], Value) then
        if LowerCase(Value) = LowerCase('{#MyAppExeName}') then
          RegDeleteValue(HKEY_CURRENT_USER, Base + '\OpenWithList', Names[I]);
  if RegQueryStringValue(HKEY_CURRENT_USER, Base + '\UserChoice', 'ProgId', Value) then
    if (Value = 'UMP.MediaFile') or (Pos(LowerCase('{#MyAppExeName}'), LowerCase(Value)) > 0) then
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, Base + '\UserChoice');
end;

{ --- دالة التنظيف التلقائي العنيفة عند الإزالة (Uninstall) --- }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ExtString, Ext: String;
  P: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    { إزالة جميع مفاتيح البرنامج من مسارات الريجيستري الرئيسية للمستخدم والنظام }
    RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, 'Directory\shell\UMPConvertDir');
    RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, 'UMP.MediaFile');
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'Software\Universal Media Player');
    RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Universal Media Player');
    RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Classes\Applications\{#MyAppExeName}');
    RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, 'Applications\{#MyAppExeName}');
    CleanMuiCache();

    ExtString := GetExtensionList();
    
    while Length(ExtString) > 0 do
    begin
      P := Pos('|', ExtString);
      if P > 0 then
      begin
        Ext := Copy(ExtString, 1, P - 1);
        Delete(ExtString, 1, P);
        
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, 'SystemFileAssociations\' + Ext + '\shell\UMPPlay');
        RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT, 'SystemFileAssociations\' + Ext + '\shell\UMPConvert');
        RegDeleteValue(HKEY_CLASSES_ROOT, Ext + '\OpenWithProgIds', 'UMP.MediaFile');
        CleanWindowsGeneratedKeys(Ext);
      end;
    end;
  end;
end;

[Run]
; تسخين المحرك: البرنامج بيقرا مكتبات VLC مرة ويخرج من غير نافذة، فأول فتح
; حقيقي بعد التثبيت يبقى أسرع (شوف main.py: --warmup)
Filename: "{app}\{#MyAppExeName}"; Parameters: "--warmup"; StatusMsg: "{cm:WarmingUp}"; Flags: runhidden waituntilterminated
; ربط وصف التشغيل بعد التثبيت بالترجمة
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{cm:AppName}}"; Flags: nowait postinstall skipifsilent

[Registry]
; ---------------------------------------------------------------------
; تسجيل خصائص البرنامج في النظام باستخدام الترجمة {cm:...}
; ملاحظة: خاصية (uninsdeletekey) تجبر الويندوز على مسح المفتاح تلقائياً عند الإزالة
; ---------------------------------------------------------------------
Root: HKCR; Subkey: "UMP.MediaFile"; ValueType: string; ValueName: ""; ValueData: "{cm:MediaFileDesc}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "UMP.MediaFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCR; Subkey: "UMP.MediaFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{cm:AppName}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{cm:AppDesc}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "UniversalMediaPlayer_UMP"; ValueData: "Software\Universal Media Player\Capabilities"; Flags: uninsdeletevalue

; ---------------------------------------------------------------------
; ربط الصيغ بقائمة السياق (جميعها تعتمد اعتماد كامل على مفاتيح الترجمة)
; ---------------------------------------------------------------------

; --- .mp3 ---
Root: HKCR; Subkey: ".mp3\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp3\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .wav ---
Root: HKCR; Subkey: ".wav\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wav\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .flac ---
Root: HKCR; Subkey: ".flac\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.flac\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .m4a ---
Root: HKCR; Subkey: ".m4a\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4a\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .aac ---
Root: HKCR; Subkey: ".aac\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aac\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ogg ---
Root: HKCR; Subkey: ".ogg\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogg\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .wma ---
Root: HKCR; Subkey: ".wma\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wma\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .oga ---
Root: HKCR; Subkey: ".oga\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".oga"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.oga\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .opus ---
Root: HKCR; Subkey: ".opus\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.opus\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .aiff ---
Root: HKCR; Subkey: ".aiff\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aiff"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aiff\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .aif ---
Root: HKCR; Subkey: ".aif\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aif"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.aif\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ape ---
Root: HKCR; Subkey: ".ape\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ape"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ape\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .alac ---
Root: HKCR; Subkey: ".alac\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".alac"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.alac\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .amr ---
Root: HKCR; Subkey: ".amr\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".amr"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.amr\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .caf ---
Root: HKCR; Subkey: ".caf\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".caf"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.caf\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .au ---
Root: HKCR; Subkey: ".au\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".au"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.au\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mid ---
Root: HKCR; Subkey: ".mid\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mid"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mid\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .midi ---
Root: HKCR; Subkey: ".midi\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".midi"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.midi\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ac3 ---
Root: HKCR; Subkey: ".ac3\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ac3"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ac3\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .dts ---
Root: HKCR; Subkey: ".dts\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".dts"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dts\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mka ---
Root: HKCR; Subkey: ".mka\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mka"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mka\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .weba ---
Root: HKCR; Subkey: ".weba\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".weba"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.weba\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .tta ---
Root: HKCR; Subkey: ".tta\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".tta"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.tta\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .wv ---
Root: HKCR; Subkey: ".wv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mpc ---
Root: HKCR; Subkey: ".mpc\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpc"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpc\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .spx ---
Root: HKCR; Subkey: ".spx\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".spx"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.spx\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .dsf ---
Root: HKCR; Subkey: ".dsf\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".dsf"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dsf\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .dff ---
Root: HKCR; Subkey: ".dff\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".dff"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.dff\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .voc ---
Root: HKCR; Subkey: ".voc\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".voc"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.voc\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .gsm ---
Root: HKCR; Subkey: ".gsm\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".gsm"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.gsm\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mpa ---
Root: HKCR; Subkey: ".mpa\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpa"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpa\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .tsa ---
Root: HKCR; Subkey: ".tsa\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".tsa"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.tsa\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mus ---
Root: HKCR; Subkey: ".mus\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mus"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mus\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mp4 ---
Root: HKCR; Subkey: ".mp4\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mp4\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mkv ---
Root: HKCR; Subkey: ".mkv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mkv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .avi ---
Root: HKCR; Subkey: ".avi\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.avi\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mov ---
Root: HKCR; Subkey: ".mov\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mov\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .wmv ---
Root: HKCR; Subkey: ".wmv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wmv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .flv ---
Root: HKCR; Subkey: ".flv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.flv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .webm ---
Root: HKCR; Subkey: ".webm\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.webm\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mpg ---
Root: HKCR; Subkey: ".mpg\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpg"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpg\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mpeg ---
Root: HKCR; Subkey: ".mpeg\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpeg"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpeg\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mpe ---
Root: HKCR; Subkey: ".mpe\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpe"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mpe\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mas ---
Root: HKCR; Subkey: ".mas\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mas"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mas\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .npa ---
Root: HKCR; Subkey: ".npa\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".npa"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.npa\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .m4v ---
Root: HKCR; Subkey: ".m4v\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m4v\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .3gp ---
Root: HKCR; Subkey: ".3gp\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".3gp"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.3gp\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .3g2 ---
Root: HKCR; Subkey: ".3g2\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".3g2"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.3g2\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ts ---
Root: HKCR; Subkey: ".ts\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ts"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ts\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mts ---
Root: HKCR; Subkey: ".mts\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mts"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mts\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .m2ts ---
Root: HKCR; Subkey: ".m2ts\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m2ts"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.m2ts\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .vob ---
Root: HKCR; Subkey: ".vob\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".vob"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.vob\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ogv ---
Root: HKCR; Subkey: ".ogv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .rm ---
Root: HKCR; Subkey: ".rm\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".rm"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.rm\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .rmvb ---
Root: HKCR; Subkey: ".rmvb\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".rmvb"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.rmvb\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .asf ---
Root: HKCR; Subkey: ".asf\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".asf"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.asf\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .divx ---
Root: HKCR; Subkey: ".divx\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".divx"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.divx\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .f4v ---
Root: HKCR; Subkey: ".f4v\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".f4v"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.f4v\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .mxf ---
Root: HKCR; Subkey: ".mxf\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mxf"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.mxf\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .qt ---
Root: HKCR; Subkey: ".qt\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".qt"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.qt\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .wtv ---
Root: HKCR; Subkey: ".wtv\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wtv"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.wtv\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .ogm ---
Root: HKCR; Subkey: ".ogm\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogm"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.ogm\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .y4m ---
Root: HKCR; Subkey: ".y4m\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".y4m"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.y4m\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- .nut ---
Root: HKCR; Subkey: ".nut\OpenWithProgIds"; ValueType: string; ValueName: "UMP.MediaFile"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Universal Media Player\Capabilities\FileAssociations"; ValueType: string; ValueName: ".nut"; ValueData: "UMP.MediaFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPPlay"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPlay}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPPlay"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPPlay\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPConvert"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvert}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPConvert"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "SystemFileAssociations\.nut\shell\UMPConvert\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert ""%1"""

; --- تحويل للمجلدات ---
Root: HKCR; Subkey: "Directory\shell\UMPConvertDir"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuConvertDir}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\UMPConvertDir"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\UMPConvertDir\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --convert-folder ""%1"""; Flags: uninsdeletekey