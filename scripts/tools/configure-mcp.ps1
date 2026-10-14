<#
.SYNOPSIS
Generar .vscode/mcp.json ignorado, con URLs de outputs y inputs protegidos.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command configure-mcp @PSBoundParameters