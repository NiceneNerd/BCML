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
try {
    Get-Command python 2>&1 | Out-Null
    $PythonVer = (python -V).Split()[-1]
    if ($PythonVer -lt "3.7.5") {
        throw "Python too old"
    } else {
        Write-Host "Python 3.7+ already installed, moving on..."
    }
} catch {
    Write-Host "Looks like you need Python! Downloading Python 3.7.9..."
    (New-Object Net.WebClient).DownloadFile("https://www.python.org/ftp/python/3.7.9/python-3.7.9-amd64-webinstall.exe", "$env:temp\python.exe")
    Write-Host "Downloaded Python. Extracting and installing..."
    & "$env:temp\python.exe" /passive InstallAllUsers=0 "$env:LocalAppData\Programs\Python37" CompileAll=1 PrependPath=1 Shortcuts=0 Include_Test=0 Include_launcher=0 InstallLauncherAllUsers=0 | Out-Null
    RefreshEnv.cmd | Out-Null
    Write-Host "Python all set!"
}

Write-Host "Installing latest BCML from PyPI..."
python -m pip install bcml --disable-pip-version-check --no-warn-script-location | Out-Null

Write-Host "Creating shortcut..."
$InstallDir = "$((python -m pip show bcml).Split("`n")[7].Split()[-1])\bcml"
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML.lnk")
$Shortcut.TargetPath = (Get-Command pythonw).Source
$Shortcut.Arguments = "-m bcml"
$Shortcut.Description = "BCML"
$Shortcut.IconLocation = "$InstallDir\data\bcml.ico"
$Shortcut.Save()

Write-Host "Done installing BCML!"
Write-Host "Now run use the shortcut in your Start Menu or run ``bcml`` to start using it!"
Write-Host "Press any key to exit..."
$host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
