<#
.SYNOPSIS
Verificar readiness, MCP directo autenticado y rechazo de bypass anonimo ACA.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command test-backends @PSBoundParameters