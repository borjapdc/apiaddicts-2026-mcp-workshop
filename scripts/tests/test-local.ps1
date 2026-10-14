<#
.SYNOPSIS
Ejecutar lint, tipos y pytest; -Smoke verifica ademas un Aspire ya levantado.
#>
param([switch]$Smoke, [switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command test-local @PSBoundParameters