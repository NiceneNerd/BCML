$ErrorActionPreference = "Stop"

function PromptQuit {
    Write-Host "Press any key to exit..."
    $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
    exit
}

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
    } else {
        Write-Host "Python 3.7+ already installed, moving on..."
        $Python = (Get-Command python).Source
    }
} catch {
    if (Test-Path -Path "$home\.python\python.exe") {
        Write-Host "Python already installed by BCML found. Using that, then."
        $Python = "$home\.python\python.exe"
    } else {
        Write-Host "No Python? No problem! Downloading the BCML bundle..."
        try {
            $latestRelease = Invoke-WebRequest https://github.com/NiceneNerd/BCML/releases/latest -Headers @{"Accept"="application/json"} -UseBasicParsing
            $json = $latestRelease.Content | ConvertFrom-Json
            $latestVersion = $json.tag_name
            (New-Object Net.WebClient).DownloadFile("https://github.com/NiceneNerd/BCML/releases/download/$latestVersion/bcml-win64-bundle.zip", "$env:temp\bundle.zip")
            $BundlePath = "$env:temp\bundle.zip"
        } catch {
            Write-Host $_
            Write-Error "Could not download BCML bundle. Maybe it's your internet connection."
            $UseLocal = Read-Host "If you have a downloaded BCML bundle to use offline, please enter the path to it now:"
            if ([String]::IsNullOrWhiteSpace($UseLocal)) {
                PromptQuit
            } else {
                $BundlePath = $UseLocal
            }
        }
        Write-Host "Downloaded BCML bundle. Where would you like it to be installed?"
        Write-Host "(If you leave this blank, it will default to %USERPROFILE%\.bcml)"
        Write-Host "> " -NoNewline
        $BcmlDir = Read-Host
        if ([String]::IsNullOrWhiteSpace($BcmlDir)) {
            $BcmlDir = "$home\.bcml"
        }
        try {
            Expand-Archive -Path $BundlePath -DestinationPath "$BcmlDir" -Force
            Move-Item -Path "$BcmlDir\python\*" -Destination "$BcmlDir\"
        } catch {
            Write-Error "There was a problem extracting the Python package."
            PromptQuit
        }
        $Python = "$BcmlDir\python.exe"
        Write-Host "Python is all set!"
    }
}

try {
    Write-Host "Installing latest BCML from PyPI..."
    & $Python -m pip install bcml --upgrade --disable-pip-version-check --no-warn-script-location | Out-Null
} catch {
    Write-Host $_
    Write-Error "BCML did not install successfully from PyPI."
    PromptQuit
}

try {
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
    $Desktop = Read-Host "Do you want to create a desktop shortcut? (y/n)"
    if ($Desktop -contains "y") {
        Copy-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\BCML.lnk" "$home\Desktop\BCML.lnk"
    }
    
    $UpdateShortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BCML\Update BCML.lnk")
    $UpdateShortcut.TargetPath = $Python
    $UpdateShortcut.Arguments = "-m pip install -U bcml"
    $UpdateShortcut.Description = "Update BCML"
    $UpdateShortcut.Save()
    
    Set-Content -Path "$InstallDir\Uninstall.ps1" -Value @"
    Write-Host "Uninstalling BCML..."
    & $Python -m pip uninstall bcml -y | Out-Null
    Write-Host "BCML uninstalled successfully"
    Remove-Item -Path "`$home\Desktop\BCML.lnk" -Force -ErrorAction SilentlyContinue
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
} catch {
    Write-Host "There was a problem creating shortcuts. BCML is still there; you can run it with:"
    Write-Host "$Python -m bcml"
    Write-Host "Feel free to make your own shortcut to this command."
}

Write-Host "The latest version of BCML has been installed! Go ahead and launch it from the shortcut if you wish.`n"
Write-Host "Just a reminder: I have a full time job, a Masters program, and 6 children."
Write-Host "So if you like what I do, consider supporting my Patreon (link above)."
Write-Host "It's what convinces my wife (partially) this is all worth the time.`n"
PromptQuit
