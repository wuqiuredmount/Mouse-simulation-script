# 在桌面创建 AI 助手快捷方式（控制面板设为管理员运行）
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell

function Set-RunAsAdmin($lnkPath) {
    # 修改 .lnk 第 0x15 字节第 5 位 = “以管理员身份运行”
    $bytes = [System.IO.File]::ReadAllBytes($lnkPath)
    $bytes[0x15] = $bytes[0x15] -bor 0x20
    [System.IO.File]::WriteAllBytes($lnkPath, $bytes)
}

function New-Shortcut($name, $target, $workdir, $icon, $admin) {
    $lnk = Join-Path $desktop ($name + '.lnk')
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = $target
    $sc.WorkingDirectory = $workdir
    if ($icon) { $sc.IconLocation = $icon }
    $sc.Save()
    if ($admin) { Set-RunAsAdmin $lnk }
    $tag = if ($admin) { '  [管理员]' } else { '' }
    Write-Host ('已创建: ' + $lnk + $tag)
}

New-Shortcut 'AI助手-控制面板' (Join-Path $root '启动助手.bat') $root "$env:SystemRoot\System32\shell32.dll,167" $true
New-Shortcut 'AI助手-抓取模板' (Join-Path $root '抓取模板.bat') $root "$env:SystemRoot\System32\shell32.dll,71" $true

Write-Host '完成。'
