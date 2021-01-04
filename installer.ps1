$ErrorActionPreference = "Stop"
Write-Host "███████████████████████████████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  ______  _____ ___  ___ _" -ForegroundColor White

Write-Host "██████████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#*#" -ForegroundColor Yellow -NoNewLine  -BackgroundColor DarkGray
Write-Host "██████████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  | ___ \/  __ \|  \/  || |" -ForegroundColor White

Write-Host "████████████████" -ForegroundColor DarkGray -NoNewLine  -BackgroundColor DarkGray
Write-Host "##***#" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "█████████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  | |_/ /| /  \/| .  . || |" -ForegroundColor White

Write-Host "███████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#******(#" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "███████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  | ___ \| |    | |\/| || |" -ForegroundColor White

Write-Host "█████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "&#*********#" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "██████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  | |_/ /| \__/\| |  | || |____" -ForegroundColor White

Write-Host "████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#/***********##" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  \____/  \____/\_|  |_/\_____/" -ForegroundColor White

Write-Host "███████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#***************#" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "███████████" -ForegroundColor DarkGray -BackgroundColor DarkGray

Write-Host "█████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "##*****************##" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "█████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  BOTW Cross-Platform Mod Loader"

Write-Host "████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#***/" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "█████████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "(///#" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "████████" -ForegroundColor DarkGray -NoNewLine
Write-Host "  Windows Installer"

Write-Host "██████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "##*****/" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "██████████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "%(/////#%" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "██████" -ForegroundColor DarkGray -BackgroundColor DarkGray

Write-Host "█████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#*********/" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "███████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "(/////////#" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "█████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  By Caleb Smith (Nicene Nerd)"

Write-Host "███" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "##***********/" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "████" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "&(///////////#&" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "███" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  https://calebdixonsmith.wordpress.com"

Write-Host "██" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#**************//" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "█" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "(//////////////##" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "██" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "  https://www.patreon.com/nicenenerdbcml"

Write-Host "█" -ForegroundColor DarkGray -NoNewLine -BackgroundColor DarkGray
Write-Host "#*****************" -ForegroundColor Yellow -NoNewLine -BackgroundColor DarkGray
Write-Host "(/////////////////#" -ForegroundColor Blue -NoNewLine -BackgroundColor DarkGray
Write-Host "█" -ForegroundColor DarkGray

Write-Host "███████████████████████████████████████" -ForegroundColor DarkGray

Write-Host "`nChecking for Python..."
$Python = ""
try {
    Get-Command python 2>&1 | Out-Null
    $PythonVer = (python -V).Split()[-1]
    if ($PythonVer -lt "3.7.5") {
        throw "Python too old"
    }
    else {
        Write-Host "Python 3.7+ already installed, moving on..."
        $Python = (Get-Command python).Source
    }
}
catch {
    Write-Host "Looks like you need Python! Downloading Python 3.7.9..."
    (New-Object Net.WebClient).DownloadFile("https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip", "$env:temp\python.zip")
    Write-Host "Downloaded Python. Extracting..."
    Expand-Archive -Path "$env:temp\python.zip" -DestinationPath "$home\.python"
    $Python = "$home\.python\python.exe"
    Write-Host "Setting up pip..."
    (New-Object Net.WebClient).DownloadFile("https://bootstrap.pypa.io/get-pip.py", "$home\.python\get-pip.py") | Out-Null
    & $Python "$home\.python\get-pip.py" --disable-pip-version-check --no-warn-script-location | Out-Null
    Set-Content -Path "$home\.python\python37._pth" -Value "python37.zip`n.`n.\Lib`n.\Lib\site-packages`n.\DLLs`n"
    Write-Host "Python is all set!"
}

Write-Host "Installing latest BCML from PyPI..."
& $Python -m pip install bcml --disable-pip-version-check --no-warn-script-location | Out-Null

Write-Host "Creating shortcuts..."
New-Item -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Name "BCML" -ItemType "directory" -ErrorAction SilentlyContinue | Out-Null
$ShowOutput = (& $Python -m pip show bcml).Split("`n")[7].Split()[-1]
$InstallDir = "$ShowOutput\bcml"
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\BCML.lnk")
$Shortcut.TargetPath = $Python.Replace("python.exe", "pythonw.exe")
$Shortcut.Arguments = "-m bcml"
$Shortcut.Description = "BCML"
$Shortcut.IconLocation = "$InstallDir\data\bcml.ico"
$Shortcut.Save()
Copy-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\BCML.lnk" "$home\Desktop\BCML.lnk"

$UpdateShortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\Update BCML.lnk")
$UpdateShortcut.TargetPath = $Python
$UpdateShortcut.Arguments = "-m pip install -U bcml"
$UpdateShortcut.Description = "Update BCML"
$UpdateShortcut.Save()

Set-Content -Path "$InstallDir\Uninstall.ps1" -Value @"
Write-Host "Uninstalling BCML..."
& $Python -m pip uninstall bcml -y | Out-Null
Remove-Item -Path "`$home\Desktop\BCML.lnk"
Remove-Item -Path "`$home\.python" -ErrorAction SilentlyContinue -Recurse -Force | Out-Null
Write-Host "BCML uninstalled successfully"
Remove-Item -Path "`$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\BCML.lnk"
Remove-Item -Path "`$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\Uninstall.lnk"
Remove-Item -Path "`$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\Update BCML.lnk"
Remove-Item -Path "`$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML" -Force -ErrorAction SilentlyContinue
Write-Host "Press any key to exit..."
`$host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
"@
$UninstallShortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\Uninstall.lnk")
$UninstallShortcut.TargetPath = (Get-Command powershell).Source
$UninstallShortcut.Arguments = "$InstallDir\Uninstall.ps1"
$UninstallShortcut.Description = "Uninstall"
$UninstallShortcut.Save()

Write-Host "BCML has been installed! Go ahead and launch it from the shortcut if you wish.`n"
Write-Host "Just a reminder: I have a full time job, a Masters program, and 6 children."
Write-Host "So if you like what I do, consider supporting my Patreon (link above)."
Write-Host "It's what convinces my wife (partially) this is all worth the time.`n"
Write-Host "Press any key to exit..."
$host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
