# Windows: in PowerShell im Ordner trading-bot ausführen:  powershell -ExecutionPolicy Bypass -File scheduler\install_windows.ps1
$dir = (Resolve-Path "$PSScriptRoot\..").Path
$action = New-ScheduledTaskAction -Execute "$dir\.venv\Scripts\python.exe" -Argument "-m src.tick" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "TradingBotTick" -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Geplanter Task 'TradingBotTick' alle 30 Minuten eingerichtet."
