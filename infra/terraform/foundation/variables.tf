variable "subscription_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.subscription_id)) && var.subscription_id != "00000000-0000-0000-0000-000000000000"
    error_message = "Use the detected MVP subscription ID, never the example GUID."
  }
}
variable "tenant_id" { type = string }
variable "location" { type = string }
variable "project" {
  type    = string
  default = "apiaddicts-mcp"
  validation {
    condition     = strcontains(lower(var.project), "apiaddicts")
    error_message = "The dedicated workshop resource group must include apiaddicts."
  }
}
variable "environment" {
  type    = string
  default = "demo"
}
variable "owner_alias" {
  type    = string
  default = "mvp-workshop"
}
variable "instance" {
  type    = string
  default = "01"
}
variable "unique_suffix" {
  type    = string
  default = ""
  validation {
    condition     = var.unique_suffix == "" || can(regex("^[a-z0-9]{6,8}$", var.unique_suffix))
    error_message = "Use 6-8 lowercase alphanumeric characters, or empty for a state-persisted suffix."
  }
}
variable "apim_sku" {
  type    = string
  default = "Developer"
  validation {
    condition     = contains(["Developer", "BasicV2"], var.apim_sku)
    error_message = "Only Developer or explicitly cost-approved BasicV2 are supported."
  }
}
variable "publisher_email" {
  type    = string
  default = "workshop@example.invalid"
}
variable "ttl" {
  type    = string
  default = "2026-10-14"
}