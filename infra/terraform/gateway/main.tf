locals {
  native = {
    "mcp-catalog"    = { product = "reader", origin_secret = "origin-read" }
    "mcp-operations" = { product = "operator", origin_secret = "origin-write" }
  }
  servers = merge(local.native, { "mcp-catalog-from-rest" = { product = "reader", origin_secret = "origin-read" } })
  tools = {
    search_services      = "Search the synthetic corporate catalog"
    get_service          = "Get a synthetic service and its fictitious SLA"
    list_versions        = "List synthetic service versions"
    get_service_contract = "Read the illustrative service OpenAPI contract"
  }
}
resource "azurerm_api_management_product" "consumer" {
  for_each              = toset(["reader", "operator"])
  product_id            = each.key
  api_management_name   = var.foundation.apim_name
  resource_group_name   = var.foundation.resource_group_name
  display_name          = "Workshop ${each.key}"
  subscription_required = true
  approval_required     = false
  published             = true
}
resource "azurerm_api_management_subscription" "consumer" {
  for_each            = azurerm_api_management_product.consumer
  subscription_id     = "workshop-${each.key}"
  resource_group_name = var.foundation.resource_group_name
  api_management_name = var.foundation.apim_name
  product_id          = each.value.id
  display_name        = "Synthetic ${each.key} consumer"
  state               = "active"
  allow_tracing       = false
}
resource "azurerm_api_management_named_value" "read" {
  name                = "origin-read"
  resource_group_name = var.foundation.resource_group_name
  api_management_name = var.foundation.apim_name
  display_name        = "origin-read"
  secret              = true
  value               = var.backend_read_token
}
resource "azurerm_api_management_named_value" "write" {
  name                = "origin-write"
  resource_group_name = var.foundation.resource_group_name
  api_management_name = var.foundation.apim_name
  display_name        = "origin-write"
  secret              = true
  value               = var.backend_write_token
}
resource "azurerm_api_management_api" "rest" {
  name                  = "catalog-rest"
  resource_group_name   = var.foundation.resource_group_name
  api_management_name   = var.foundation.apim_name
  revision              = "1"
  display_name          = "Synthetic Corporate Catalog REST"
  path                  = "catalog"
  protocols             = ["https"]
  service_url           = var.backends["catalog-api"]
  subscription_required = true
  import {
    content_format = "openapi+json"
    content_value  = file("${path.module}/catalog.openapi.json")
  }
}
resource "azurerm_api_management_api_policy" "rest" {
  api_name            = azurerm_api_management_api.rest.name
  api_management_name = var.foundation.apim_name
  resource_group_name = var.foundation.resource_group_name
  xml_content         = file("${path.module}/policies/rest.xml")
  depends_on          = [azurerm_api_management_named_value.read]
}
resource "azurerm_api_management_product_api" "rest" {
  api_name            = azurerm_api_management_api.rest.name
  product_id          = azurerm_api_management_product.consumer["reader"].product_id
  api_management_name = var.foundation.apim_name
  resource_group_name = var.foundation.resource_group_name
}
resource "azurerm_api_management_backend" "native" {
  for_each            = local.native
  name                = "${each.key}-origin"
  resource_group_name = var.foundation.resource_group_name
  api_management_name = var.foundation.apim_name
  protocol            = "http"
  url                 = "${var.backends[each.key]}/mcp"
  tls {
    validate_certificate_chain = true
    validate_certificate_name  = true
  }
}
resource "azapi_resource" "native" {
  for_each                  = local.native
  type                      = "Microsoft.ApiManagement/service/apis@2025-09-01-preview"
  name                      = each.key
  parent_id                 = var.foundation.apim_id
  schema_validation_enabled = false
  create_headers            = { "If-Match" = "*" }
  update_headers            = { "If-Match" = "*" }
  delete_headers            = { "If-Match" = "*" }
  locks                     = [var.foundation.apim_id]
  body = {
    properties = {
      type          = "mcp", displayName = each.key, path = "${each.key}/mcp",
      protocols     = ["https"], subscriptionRequired = true,
      serviceUrl    = var.backends[each.key],
      backendId     = azurerm_api_management_backend.native[each.key].name,
      mcpProperties = { transportType = "streamable", endpoints = { message = { uriTemplate = "/mcp" } } }
    }
  }
  response_export_values = ["properties.path", "properties.mcpProperties", "properties.serviceUrl"]
}
resource "azapi_resource" "from_rest" {
  type      = "Microsoft.ApiManagement/service/apis@2025-09-01-preview"
  name      = "mcp-catalog-from-rest"
  parent_id = var.foundation.apim_id
  body = {
    properties = {
      type      = "mcp", displayName = "mcp-catalog-from-rest", path = "mcp-catalog-from-rest",
      protocols = ["https"], subscriptionRequired = true
    }
  }
  response_export_values = ["properties.path"]
}
resource "azapi_resource" "tool" {
  for_each       = local.tools
  type           = "Microsoft.ApiManagement/service/apis/tools@2025-09-01-preview"
  name           = each.key
  parent_id      = azapi_resource.from_rest.id
  create_headers = { "If-Match" = "*" }
  update_headers = { "If-Match" = "*" }
  delete_headers = { "If-Match" = "*" }
  locks          = [var.foundation.apim_id]
  body = {
    properties = {
      displayName = each.key, description = each.value,
      operationId = "${var.foundation.apim_id}/apis/${azurerm_api_management_api.rest.name}/operations/${each.key}"
    }
  }
  depends_on = [azurerm_api_management_api_policy.rest]
}
locals {
  mcp_ids = merge({ for name, api in azapi_resource.native : name => api.id }, { "mcp-catalog-from-rest" = azapi_resource.from_rest.id })
}
resource "azapi_resource" "policy" {
  for_each  = local.servers
  type      = "Microsoft.ApiManagement/service/apis/policies@2025-09-01-preview"
  name      = "policy"
  parent_id = local.mcp_ids[each.key]
  body = {
    properties = {
      format = "xml"
      value = templatefile("${path.module}/policies/${each.key == "mcp-catalog-from-rest" ? "rest-mcp" : "mcp"}.xml.tftpl", {
        product = each.value.product, origin_secret = each.value.origin_secret,
        calls   = var.rate_limit_calls, period = var.rate_limit_period_seconds
      })
    }
  }
  depends_on = [azurerm_api_management_named_value.read, azurerm_api_management_named_value.write]
}
resource "azurerm_api_management_product_api" "binding" {
  for_each            = local.servers
  api_name            = each.key
  product_id          = azurerm_api_management_product.consumer[each.value.product].product_id
  api_management_name = var.foundation.apim_name
  resource_group_name = var.foundation.resource_group_name
  depends_on          = [azapi_resource.native, azapi_resource.from_rest]
}
resource "azurerm_api_management_logger" "insights" {
  name                = "workshop-insights"
  api_management_name = var.foundation.apim_name
  resource_group_name = var.foundation.resource_group_name
  resource_id         = var.foundation.app_insights_id
  application_insights {
    instrumentation_key = var.app_insights_instrumentation_key
  }
}
resource "azapi_resource" "diagnostic" {
  for_each  = local.servers
  type      = "Microsoft.ApiManagement/service/apis/diagnostics@2025-09-01-preview"
  name      = "applicationinsights"
  parent_id = local.mcp_ids[each.key]
  body = {
    properties = {
      loggerId  = azurerm_api_management_logger.insights.id,
      alwaysLog = "allErrors", sampling = { samplingType = "fixed", percentage = 100 },
      verbosity = "information", httpCorrelationProtocol = "W3C", logClientIp = false,
      frontend  = { request = { body = { bytes = 0 }, headers = [] }, response = { body = { bytes = 0 }, headers = [] } },
      backend   = { request = { body = { bytes = 0 }, headers = [] }, response = { body = { bytes = 0 }, headers = [] } }
    }
  }
}
resource "azurerm_monitor_diagnostic_setting" "gateway" {
  count                          = var.enable_resource_logs ? 1 : 0
  name                           = "workshop-gateway-logs"
  target_resource_id             = var.foundation.apim_id
  log_analytics_workspace_id     = var.foundation.log_workspace_id
  log_analytics_destination_type = "Dedicated"
  enabled_log { category = "GatewayLogs" }
}