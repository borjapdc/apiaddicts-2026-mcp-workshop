<#
.SYNOPSIS
Planificar por defecto; -Apply crea recursos exclusivamente en MVP. -WhatIf explicita plan-only.
#>
param([switch]$Apply, [switch]$WhatIf, [switch]$Help, [string]$Location)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command deploy @PSBoundParameters