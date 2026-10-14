<#
.SYNOPSIS
Plan de destruccion por defecto. -Apply requiere ConfirmGroup y ConfirmSubscription exactos; destructivo.
#>
param([switch]$Apply, [switch]$WhatIf, [switch]$Help, [string]$ConfirmGroup, [string]$ConfirmSubscription)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command destroy @PSBoundParameters