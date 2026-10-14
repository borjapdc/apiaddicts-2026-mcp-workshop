<#
.SYNOPSIS
Carga MCP pequena con 429 observado y recuperacion tras ventana.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command load @PSBoundParameters