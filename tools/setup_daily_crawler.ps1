$ActionName = "InternshipFinderCrawler"
$ActionDescription = "Daily scheduled task for Internship Finder crawlers and data pipeline."
$ScriptPath = Join-Path $PSScriptRoot "run_pipeline.bat"

# Define Trigger (Runs every day at 02:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

# Define Action
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$ScriptPath`"" -WorkingDirectory $PSScriptRoot

# Define Settings (Run even if user is not logged on, wake to run)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 4)

# Register the task
Register-ScheduledTask -Action $Action -Trigger $Trigger -TaskName $ActionName -Description $ActionDescription -Settings $Settings -User "SYSTEM" -Force

Write-Host "Scheduled task '$ActionName' has been successfully created."
Write-Host "It will run daily at 02:00 AM using $ScriptPath."
