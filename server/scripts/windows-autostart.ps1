[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Remove')]
    [string] $Action,

    [Parameter(Mandatory = $false)]
    [string] $ExecutablePath
)

$taskName = 'Android Stream Deck Tray'

if ($Action -eq 'Remove') {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ExecutablePath)) {
    throw 'ExecutablePath is required for Install.'
}

$resolved = Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop
if ([IO.Path]::GetFileName($resolved.Path) -ne 'streamdeck-tray.exe') {
    throw 'ExecutablePath must point to streamdeck-tray.exe.'
}

$actionDefinition = New-ScheduledTaskAction -Execute $resolved.Path
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $actionDefinition -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Output "Autostart instalado: $taskName"
