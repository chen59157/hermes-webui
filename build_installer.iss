; Hermes WebUI 安装包脚本
; 编译: ISCC.exe build_installer.iss

#define MyAppName "Hermes WebUI"
#define MyAppVersion "3.2.0"
#define MyAppPublisher "Hermes Project"
#define MyAppURL "https://github.com/hermes"
#define MyAppExeName "启动 Hermes WebUI.bat"

[Setup]
AppId={{A8F3C9E2-1B5D-4A3E-9F72-D8E4B6C1A0F7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=D:\桌面\非~主要\Hermes-WebUI\使用说明.txt
OutputDir=D:\桌面\非~主要\Hermes-WebUI\dist
OutputBaseFilename=HermesWebUI_Setup_v3.2.0
SetupIconFile=D:\桌面\非~主要\Hermes-WebUI\hermes-icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
UninstallDisplayIcon={app}\hermes-icon.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
chinesesimp.WelcomeLabel2=即将安装 [name] v[version] 到您的电脑。%n%n建议安装在 C 盘以获得最佳运行性能。

[Types]
Name: "full"; Description: "完整安装"
Name: "compact"; Description: "最小安装"
Name: "custom"; Description: "自定义安装"; Flags: iscustom

[Components]
Name: "main"; Description: "主程序 (必需)"; Types: full compact custom; Flags: fixed
Name: "desktopicon"; Description: "桌面快捷方式"; Types: full
Name: "startmenu"; Description: "开始菜单快捷方式"; Types: full
Name: "autostart"; Description: "开机自启动"; Types: full

[Files]
; 主程序文件
Source: "D:\桌面\非~主要\Hermes-WebUI\hermes_desktop.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\hermes-icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\SOUL.md"; DestDir: "{app}"; Flags: ignoreversion

; 优化文件 - 设计系统和UI组件
Source: "D:\桌面\非~主要\Hermes-WebUI\design-system.css"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\ui-components.css"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\ui-components.js"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\桌面\非~主要\Hermes-WebUI\loading.html"; DestDir: "{app}"; Flags: ignoreversion

; WebUI 前端
Source: "D:\桌面\非~主要\Hermes-WebUI\hermes-webui-cn\*"; DestDir: "{app}\hermes-webui-cn"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,node_modules,.git,*.dist-info\*"

; Agent 后端 (含 venv)
Source: "D:\桌面\非~主要\Hermes-WebUI\hermes-agent\*"; DestDir: "{app}\hermes-agent"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,.git,*.dist-info\*,*.md,RELEASE_*.md,CONTRIBUTING.md,Dockerfile,docker-compose*,.dockerignore,uv.lock,.python-version"

; HermesWarden 任务守护进程
Source: "D:\桌面\非~主要\Hermes-WebUI\hermes-warden\*"; DestDir: "{app}\hermes-warden"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,.git,*.dist-info\*,.env"

; 运行时
Source: "D:\桌面\非~主要\Hermes-WebUI\tk_runtime\*"; DestDir: "{app}\tk_runtime"; Flags: ignoreversion recursesubdirs createallsubdirs

; 数据目录
; 数据目录（排除真实 .env，保护 API Key）
Source: "D:\桌面\非~主要\Hermes-WebUI\.hermes\*"; DestDir: "{app}\.hermes"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".env"; Check: DirExists(ExpandConstant('D:\桌面\非~主要\Hermes-WebUI\.hermes'))
; 安全的 .env 模板（不含真实 API Key）
Source: "D:\桌面\非~主要\Hermes-WebUI\.hermes\env_template"; DestDir: "{app}\.hermes"; DestName: ".env"; Flags: ignoreversion onlyifdoesntexist
; 配置示例文件
Source: "D:\桌面\非~主要\Hermes-WebUI\.env.example"; DestDir: "{app}\.hermes"; Flags: ignoreversion

; Python 运行时 (无需系统安装 Python)
Source: "D:\桌面\非~主要\Hermes-WebUI\python-runtime\*"; DestDir: "{app}\python-runtime"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.dist-info\*,test_*.py"

[Dirs]
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\hermes-agent\.venv\Scripts\pythonw.exe"; Parameters: """{app}\hermes_desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\hermes-icon.ico"; Components: startmenu
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; Components: startmenu
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\hermes-agent\.venv\Scripts\pythonw.exe"; Parameters: """{app}\hermes_desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\hermes-icon.ico"; Components: desktopicon

[Run]
Filename: "{app}\hermes-agent\.venv\Scripts\pythonw.exe"; Parameters: """{app}\hermes_desktop.py"""; WorkingDir: "{app}"; Description: "启动 {#MyAppName}"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM pythonw.exe /T"; Flags: runhidden skipifdoesntexist; RunOnceId: "killPythonW"

[Code]
const
  CSIDL_DESKTOPDIRECTORY = $0010;
  MAX_PATH = 260;

function SHGetSpecialFolderPath(hwnd: HWND; lpszPath: string; csidl: Integer; fCreate: Boolean): Boolean;
external 'SHGetSpecialFolderPathW@shell32.dll stdcall';

procedure FixVenvPath();
var
  PyvenvCfg, PythonHome, PythonExe, ConfigContent: string;
begin
  PyvenvCfg := ExpandConstant('{app}\hermes-agent\.venv\pyvenv.cfg');
  if not FileExists(PyvenvCfg) then Exit;

  PythonHome := ExpandConstant('{app}\python-runtime');
  PythonExe := PythonHome + '\pythonw.exe';

  Log('使用内置 Python 运行时: ' + PythonHome);

  ConfigContent :=
    'home = ' + PythonHome + #13#10 +
    'include-system-site-packages = false' + #13#10 +
    'version = 3.12.10' + #13#10 +
    'executable = ' + PythonExe + #13#10;

  if SaveStringToFile(PyvenvCfg, ConfigContent, False) then
    Log('pyvenv.cfg 已更新')
  else
    Log('错误: 无法写入 pyvenv.cfg');
end;

// 创建启动批处理（只启动 hermes_desktop.py，warden 由它内部自动启动）
procedure CreateStartupBat();
var
  BatPath, BatContent: string;
begin
  BatPath := ExpandConstant('{app}\{#MyAppExeName}');
  BatContent :=
    '@echo off' + #13#10 +
    'chcp 65001 >nul 2>&1' + #13#10 +
    'cd /d "' + ExpandConstant('{app}') + '"' + #13#10 +
    'start "" "' + ExpandConstant('{app}') + '\hermes-agent\.venv\Scripts\pythonw.exe" "' + ExpandConstant('{app}') + '\hermes_desktop.py"' + #13#10;

  if not SaveStringToFile(BatPath, BatContent, False) then
    Log('警告: 无法创建启动脚本');
end;

// 创建用户桌面快捷方式（解决 D:\桌面 等非标准桌面路径问题）
procedure CreateUserDesktopShortcut();
var
  UserDesktop, ShortcutPath, PythonwPath, ScriptPath, IconPath: string;
begin
  // 获取当前用户真实桌面路径
  SetLength(UserDesktop, MAX_PATH);
  if not SHGetSpecialFolderPath(0, UserDesktop, CSIDL_DESKTOPDIRECTORY, False) then
  begin
    Log('无法获取用户桌面路径，跳过用户桌面快捷方式创建');
    Exit;
  end;
  // 去掉尾部 null 字符
  while (Length(UserDesktop) > 0) and (UserDesktop[Length(UserDesktop)] = #0) do
    SetLength(UserDesktop, Length(UserDesktop) - 1);

  ShortcutPath := UserDesktop + '\Hermes WebUI.lnk';
  if FileExists(ShortcutPath) then
  begin
    Log('用户桌面快捷方式已存在: ' + ShortcutPath);
    Exit;
  end;

  // 直接指向 pythonw.exe（避免 .bat 黑窗闪烁）
  PythonwPath := ExpandConstant('{app}\hermes-agent\.venv\Scripts\pythonw.exe');
  ScriptPath := ExpandConstant('{app}\hermes_desktop.py');
  IconPath := ExpandConstant('{app}\hermes-icon.ico');

  Log('创建用户桌面快捷方式: ' + ShortcutPath + ' → ' + PythonwPath);
  try
    CreateShellLink(ShortcutPath, '"' + ScriptPath + '"', PythonwPath, '', ExpandConstant('{app}'), IconPath, 0, 0);
    Log('用户桌面快捷方式创建成功');
  except
    Log('用户桌面快捷方式创建失败');
  end;
end;


// ============================================================
// WebView2 Runtime 检测与静默安装
// ============================================================
function IsWebView2Installed(): Boolean;
var
  RegVersion: string;
begin
  Result := False;
  // 检查 WebView2 Evergreen Runtime 注册表
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEB-235B8DB51B8F}', 'pv', RegVersion) then
  begin
    Log('WebView2 Runtime 版本: ' + RegVersion);
    Result := True;
    Exit;
  end;
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEB-235B8DB51B8F}', 'pv', RegVersion) then
  begin
    Log('WebView2 Runtime 版本: ' + RegVersion);
    Result := True;
    Exit;
  end;
  // 也检查 HKCU（当前用户安装）
  if RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEB-235B8DB51B8F}', 'pv', RegVersion) then
  begin
    Log('WebView2 Runtime 版本 (用户): ' + RegVersion);
    Result := True;
    Exit;
  end;
  Log('WebView2 Runtime 未检测到');
end;

procedure InstallWebView2();
var
  ResultCode: Integer;
  BootstrapperPath: string;
  DownloadPage: TDownloadWizardPage;
begin
  Log('正在安装 WebView2 Runtime...');
  BootstrapperPath := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');

  // 下载 WebView2 Evergreen Bootstrapper（约 1.7MB）
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
  DownloadPage.Clear;
  DownloadPage.Add('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '');
  DownloadPage.Show;

  try
    DownloadPage.Download;
  except
    Log('WebView2 下载失败: ' + GetExceptionMessage);
    DownloadPage.Hide;
    MsgBox('WebView2 Runtime 下载失败。' + #13#10#13#10 +
           '请手动下载安装: https://developer.microsoft.com/en-us/microsoft-edge/webview2/' + #13#10#13#10 +
           '安装完成后，Hermes WebUI 即可正常使用。',
           mbError, MB_OK);
    Exit;
  end;

  DownloadPage.Hide;

  // 静默安装 WebView2
  if Exec(BootstrapperPath, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
      Log('WebView2 Runtime 安装成功')
    else
      Log('WebView2 安装返回码: ' + IntToStr(ResultCode));
  end
  else
    Log('WebView2 安装执行失败: ' + SysErrorMessage(DLLGetLastError));

  // 清理临时文件
  DeleteFile(BootstrapperPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    // 安装 WebView2 Runtime（如需要）
    if not IsWebView2Installed() then
    begin
      Log('安装 WebView2 Runtime...');
      InstallWebView2();
    end;
  end;

  if CurStep = ssPostInstall then
  begin
    Log('安装后处理: 修复 venv 路径...');
    FixVenvPath();
    Log('安装后处理: 创建启动脚本...');
    CreateStartupBat();
    Log('安装后处理: 创建用户桌面快捷方式...');
    CreateUserDesktopShortcut();
  end;
end;

// 安装完成页面
procedure CurPageChanged(CurPageID: Integer);
begin
  // 内置 Python 运行时，无需检测系统 Python
end;

// 检查是否有旧版本运行
function InitializeSetup(): Boolean;
begin
  Result := True;
  if MsgBox('安装前请确保已关闭所有 Hermes WebUI 窗口。' + #13#10#13#10 + '是否继续？', mbConfirmation, MB_YESNO) = IDNO then
  begin
    Result := False;
    Exit;
  end;

  // 检测 WebView2 Runtime
  if not IsWebView2Installed() then
  begin
    Log('WebView2 未安装，将在安装过程中自动安装');
    MsgBox('检测到您的电脑未安装 WebView2 运行时。' + #13#10#13#10 +
           '安装程序将自动下载并安装（约 150MB，需要网络连接）。' + #13#10 +
           '这是一次性操作，安装完成后即可正常使用。',
           mbInformation, MB_OK);
  end;
end;