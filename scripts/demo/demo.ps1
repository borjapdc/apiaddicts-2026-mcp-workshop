<#
.SYNOPSIS
Ejecutar un bloque de la narrativa discover, cloud, govern o foundry sin modelos comerciales.
#>
param([ValidateSet('discover','cloud','govern','foundry')][string]$Step = 'discover', [switch]$Help, [switch]$Json)
. "$PSScriptRoot/../lib/common.ps1"
Invoke-Workshop -Command demo @PSBoundParameters