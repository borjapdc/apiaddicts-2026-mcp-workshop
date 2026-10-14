<#
.SYNOPSIS
Consultar dimensiones MCP reales en AppRequests de Log Analytics.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command observe @PSBoundParameters