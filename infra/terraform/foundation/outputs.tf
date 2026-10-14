output "foundation" {
  value = {
    subscription_id      = var.subscription_id
    tenant_id            = var.tenant_id
    location             = var.location
    resource_group_name  = azurerm_resource_group.workshop.name
    resource_group_id    = azurerm_resource_group.workshop.id
    workshop_instance_id = local.stem
    unique_suffix        = local.suffix
    app_base             = local.short
    acr_name             = azurerm_container_registry.images.name
    acr_login_server     = azurerm_container_registry.images.login_server
    acr_id               = azurerm_container_registry.images.id
    pull_identity_id     = azurerm_user_assigned_identity.pull.id
    environment_id       = azurerm_container_app_environment.apps.id
    environment_domain   = azurerm_container_app_environment.apps.default_domain
    apim_name            = azurerm_api_management.gateway.name
    apim_id              = azurerm_api_management.gateway.id
    gateway_url          = azurerm_api_management.gateway.gateway_url
    app_insights_id      = azurerm_application_insights.telemetry.id
    app_insights_app_id  = azurerm_application_insights.telemetry.app_id
    log_workspace_id     = azurerm_log_analytics_workspace.logs.id
    log_workspace_guid   = azurerm_log_analytics_workspace.logs.workspace_id
    tags                 = local.tags
  }
  depends_on = [azurerm_role_assignment.pull]
}
output "backend_read_token" {
  value     = random_password.read.result
  sensitive = true
}
output "backend_write_token" {
  value     = random_password.write.result
  sensitive = true
}
output "app_insights_instrumentation_key" {
  value     = azurerm_application_insights.telemetry.instrumentation_key
  sensitive = true
}