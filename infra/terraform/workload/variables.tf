variable "subscription_id" { type = string }
variable "tenant_id" { type = string }
variable "foundation" {
  type = object({
    subscription_id      = string, tenant_id = string, location = string, resource_group_name = string,
    workshop_instance_id = string, app_base = string, acr_login_server = string,
    pull_identity_id     = string, environment_id = string, environment_domain = string, tags = map(string)
  })
  validation {
    condition     = var.foundation.subscription_id == var.subscription_id && var.foundation.tenant_id == var.tenant_id
    error_message = "Foundation and provider targets must match exactly."
  }
}
variable "images" {
  type = map(string)
  validation {
    condition     = alltrue([for name in ["catalog-api", "mcp-catalog", "mcp-operations"] : can(var.images[name]) && !endswith(try(var.images[name], ""), ":latest")])
    error_message = "Supply all three immutable image tags or digests; latest is not allowed."
  }
}
variable "backend_read_token" {
  type      = string
  sensitive = true
}
variable "backend_write_token" {
  type      = string
  sensitive = true
}
variable "aca_min_replicas" {
  type    = number
  default = 1
  validation {
    condition     = var.aca_min_replicas >= 0 && var.aca_min_replicas <= 1
    error_message = "Workshop minimum must be 0 or 1."
  }
}
variable "aca_max_replicas" {
  type    = number
  default = 2
  validation {
    condition     = var.aca_max_replicas >= 1 && var.aca_max_replicas <= 2
    error_message = "Workshop maximum must be 1 or 2."
  }
}