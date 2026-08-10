[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Remove')]
    [string] $Action,

    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 65535)]
    [int] $Port = 8765
)

$ruleName = "Android Stream Deck TCP $Port - Private"

if ($Action -eq 'Remove') {
    Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    exit 0
}

Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile Private `
    -Description 'Android Stream Deck: explicit local-network access only.' | Out-Null

Write-Output "Regra de firewall instalada somente no perfil Private: $ruleName"
