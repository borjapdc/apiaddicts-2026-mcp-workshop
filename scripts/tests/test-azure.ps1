<#
.SYNOPSIS
Verificar MCP APIM real, equivalencia REST y aislamiento reader/operator.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command test-azure @PSBoundParameters