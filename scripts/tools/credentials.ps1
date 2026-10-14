<#
.SYNOPSIS
Dot-source para asignar reader/operator keys al environment sin imprimirlas.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
& uv --directory $root run --project $root python -m scripts.lib.workshop assert-subscription | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED subscription assertion' }
$ids = terraform "-chdir=$root/infra/terraform/gateway" output -json subscription_ids | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED gateway outputs' }
$env:APIM_READER_KEY = az rest --method post --url "https://management.azure.com$($ids.reader)/listSecrets?api-version=2025-09-01-preview" --query primaryKey -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED reader credential retrieval' }
$env:APIM_OPERATOR_KEY = az rest --method post --url "https://management.azure.com$($ids.operator)/listSecrets?api-version=2025-09-01-preview" --query primaryKey -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED operator credential retrieval' }
Write-Host 'PASS credentials assigned to environment; no keys printed'