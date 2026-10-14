<#
.SYNOPSIS
Comprobar herramientas, MVP, permisos, cuota, SKU y precios sin crear recursos.
#>
param([switch]$Help, [string]$Location)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command preflight @PSBoundParameters