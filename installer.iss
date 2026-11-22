; 工作考勤表 · Windows 安装程序脚本（Inno Setup 6）
; 编译：ISCC.exe installer.iss（输出到 release\工作考勤表_安装程序.exe）

[Setup]
AppId={{8C2E5A7B-6D31-4E1B-9F4A-2C3D6E9A0B11}
AppName=工作考勤表
AppVersion=1.0.0
AppPublisher=柯一鸣
AppCopyright=Copyright (C) 2026-present 柯一鸣
VersionInfoCompany=柯一鸣
VersionInfoDescription=工作考勤表 安装程序
VersionInfoCopyright=Copyright (C) 2026-present 柯一鸣
VersionInfoProductName=工作考勤表
VersionInfoVersion={#SetupSetting("AppVersion")}.0
DefaultDirName={localappdata}\Programs\工作考勤表
DefaultGroupName=工作考勤表
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=工作考勤表_安装程序
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app\icon.ico
UninstallDisplayIcon={app}\AttendanceDesktop.exe
UninstallDisplayName=工作考勤表

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加图标："; Flags: unchecked

[Files]
Source: "dist\AttendanceDesktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\工作考勤表"; Filename: "{app}\AttendanceDesktop.exe"
Name: "{userdesktop}\工作考勤表"; Filename: "{app}\AttendanceDesktop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AttendanceDesktop.exe"; Description: "立即运行 工作考勤表"; Flags: nowait postinstall skipifsilent
