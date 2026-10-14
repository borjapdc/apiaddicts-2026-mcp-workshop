resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}
resource "random_password" "read" {
  length  = 48
  special = false
}
resource "random_password" "write" {
  length  = 48
  special = false
}
locals {
  suffix = var.unique_suffix != "" ? var.unique_suffix : random_string.suffix.result
  parts  = [for part in [var.project, var.environment, var.owner_alias, var.instance] : trim(replace(lower(part), "/[^a-z0-9-]/", ""), "-")]
  stem   = "${substr(join("-", local.parts), 0, 36)}-${local.suffix}"
  short  = "${substr(local.parts[0], 0, 4)}-${substr(local.parts[1], 0, 3)}-${substr(local.parts[3], 0, 2)}-${local.suffix}"
  tags = {
    project = var.project, environment = var.environment, owner = var.owner_alias,
    purpose = "apiaddicts-2026-mcp-workshop", ttl = var.ttl, workshop_instance_id = local.stem
  }
}
resource "azurerm_resource_group" "workshop" {
  name     = "rg-${local.stem}"
  location = var.location
  tags     = local.tags
}
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "law-${local.stem}"
  location            = var.location
  resource_group_name = azurerm_resource_group.workshop.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1
  tags                = local.tags
}
resource "azurerm_application_insights" "telemetry" {
  name                 = "appi-${local.stem}"
  location             = var.location
  resource_group_name  = azurerm_resource_group.workshop.name
  workspace_id         = azurerm_log_analytics_workspace.logs.id
  application_type     = "web"
  daily_data_cap_in_gb = 0.1
  tags                 = local.tags
}
resource "azurerm_container_registry" "images" {
  name                = "acr${substr(replace(local.stem, "-", ""), 0, 45)}"
  resource_group_name = azurerm_resource_group.workshop.name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}
resource "azurerm_user_assigned_identity" "pull" {
  name                = "id-pull-${local.stem}"
  resource_group_name = azurerm_resource_group.workshop.name
  location            = var.location
  tags                = local.tags
}
resource "azurerm_role_assignment" "pull" {
  scope                = azurerm_container_registry.images.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pull.principal_id
  principal_type       = "ServicePrincipal"
}
resource "azurerm_container_app_environment" "apps" {
  name                       = "cae-${local.stem}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.workshop.name
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
  tags = local.tags
}
resource "azurerm_api_management" "gateway" {
  name                = "apim-${local.stem}"
  location            = var.location
  resource_group_name = azurerm_resource_group.workshop.name
  publisher_name      = "APIAddicts Synthetic Workshop"
  publisher_email     = var.publisher_email
  sku_name            = "${var.apim_sku}_1"
  identity { type = "SystemAssigned" }
  tags = local.tags
  timeouts {
    create = "90m"
    update = "90m"
    delete = "90m"
  }
}