<#
.SYNOPSIS
Normalizar XML con XmlWriter .NET al formato APIM; no cambia semantica ni ignora policy drift.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
foreach ($relative in @('infra/terraform/gateway/policies/mcp.xml.tftpl', 'infra/terraform/gateway/policies/rest.xml', 'infra/terraform/gateway/policies/rest-mcp.xml.tftpl')) {
    $path = Join-Path $root $relative
    $document = [System.Xml.XmlDocument]::new()
    $document.PreserveWhitespace = $false
    $source = if ($relative.EndsWith('/rest-mcp.xml.tftpl')) { Join-Path $root 'infra/terraform/gateway/policies/mcp.xml.tftpl' } else { $path }
    $document.LoadXml([IO.File]::ReadAllText($source))
    if ($relative.EndsWith('/rest-mcp.xml.tftpl')) {
        $header = $document.SelectSingleNode('/policies/inbound/set-header[@name="Ocp-Apim-Subscription-Key"]')
        if ($null -eq $header) { throw 'Missing subscription header rule in native policy' }
        $null = $header.ParentNode.RemoveChild($header)
    }
    $settings = [System.Xml.XmlWriterSettings]::new()
    $settings.Indent = $true
    $settings.IndentChars = "`t"
    $settings.NewLineChars = "`r`n"
    $settings.OmitXmlDeclaration = $true
    $buffer = [IO.StringWriter]::new()
    $writer = [System.Xml.XmlWriter]::Create($buffer, $settings)
    $document.Save($writer)
    $writer.Close()
    [IO.File]::WriteAllText($path, $buffer.ToString(), [Text.UTF8Encoding]::new($false))
}
Write-Host 'PASS policy XML normalized; review terraform plan for semantic changes'