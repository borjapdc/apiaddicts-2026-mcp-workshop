output "backends" {
  value = merge({
    "catalog-api" = "https://${azurerm_container_app.catalog.ingress[0].fqdn}"
  }, { for name, app in azurerm_container_app.mcp : name => "https://${app.ingress[0].fqdn}" })
}
output "container_app_ids" {
  value = merge({ "catalog-api" = azurerm_container_app.catalog.id }, { for name, app in azurerm_container_app.mcp : name => app.id })
}