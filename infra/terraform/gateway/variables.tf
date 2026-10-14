variable "subscription_id" { type = string }
variable "tenant_id" { type = string }
variable "foundation" {
  type = object({
    subscription_id = string, tenant_id = string, resource_group_name = string,
    apim_id         = string, apim_name = string, gateway_url = string,
    app_insights_id = string, log_workspace_id = string
  })
  validation {
    condition     = var.foundation.subscription_id == var.subscription_id && var.foundation.tenant_id == var.tenant_id
    error_message = "Gateway and foundation targets must match exactly."
  }
}
variable "backends" { type = map(string) }
variable "backend_read_token" {
  type      = string
  sensitive = true
}
variable "backend_write_token" {
  type      = string
  sensitive = true
}
variable "app_insights_instrumentation_key" {
  type      = string
  sensitive = true
}
variable "rate_limit_calls" {
  type    = number
  default = 5
  validation {
    condition     = var.rate_limit_calls >= 5 && var.rate_limit_calls <= 20
    error_message = "Use 5-20 requests; the official client lifecycle consumes several HTTP calls."
  }
}
variable "rate_limit_period_seconds" {
  type    = number
  default = 30
  validation {
    condition     = var.rate_limit_period_seconds >= 10 && var.rate_limit_period_seconds <= 60
    error_message = "Use a bounded demo window of 10-60 seconds."
  }
}
variable "enable_resource_logs" {
  type    = bool
  default = true
}