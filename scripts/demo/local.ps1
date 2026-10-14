<#
.SYNOPSIS
Arrancar el AppHost Aspire local con los mismos tres Dockerfiles de cloud.
#>
param([switch]$Help)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command local @PSBoundParameters