output "gateway_endpoints" {
  value = merge(
    { for name, api in azapi_resource.native : name => "${var.foundation.gateway_url}/${api.output.properties.path}" },
    { "mcp-catalog-from-rest" = "${var.foundation.gateway_url}/${azapi_resource.from_rest.output.properties.path}/mcp" }
  )
}
output "rest_url" { value = "${var.foundation.gateway_url}/${azurerm_api_management_api.rest.path}" }
output "subscription_ids" { value = { for name, subscription in azurerm_api_management_subscription.consumer : name => subscription.id } }
output "mcp_resource_ids" { value = local.mcp_ids }
output "tool_operation_ids" { value = { for name, tool in azapi_resource.tool : name => tool.body.properties.operationId } }
output "rate_limit_calls" { value = var.rate_limit_calls }
output "rate_limit_period_seconds" { value = var.rate_limit_period_seconds }