function Invoke-Workshop {
    param([string]$Command, [string]$Step, [switch]$Apply, [switch]$WhatIf,
          [switch]$Smoke, [switch]$Help, [switch]$Json, [string]$Location,
          [string]$ConfirmGroup, [string]$ConfirmSubscription)
    $ErrorActionPreference = 'Stop'
    $root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $arguments = @('run', '--project', $root, 'python', '-m', 'scripts.lib.workshop', $Command)
    if ($Step) { $arguments += @('--step', $Step) }
    if ($Apply) { $arguments += '--apply' }
    if ($WhatIf) { $arguments += '--what-if' }
    if ($Smoke) { $arguments += '--smoke' }
    if ($Help) { $arguments += '--help' }
    if ($Json) { $arguments += '--json' }
    if ($Location) { $arguments += @('--location', $Location) }
    if ($ConfirmGroup) { $arguments += @('--confirm-group', $ConfirmGroup) }
    if ($ConfirmSubscription) { $arguments += @('--confirm-subscription', $ConfirmSubscription) }
    Push-Location $root
    try {
        & uv @arguments
        $result = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $result
}