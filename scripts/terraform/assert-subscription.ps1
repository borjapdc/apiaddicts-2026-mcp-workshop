<#
.SYNOPSIS
Seleccionar solo una suscripcion Enabled con nombre MVP; bloquear ambiguedad.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command assert-subscription @PSBoundParameters