locals {
  common_env = {
    REQUIRE_AUTH = "1", CATALOG_DB = "/tmp/apiaddicts-catalog.db"
  }
  mcps = {
    "mcp-catalog"    = "ca-read-${var.foundation.app_base}"
    "mcp-operations" = "ca-ops-${var.foundation.app_base}"
  }
}
resource "azurerm_container_app" "catalog" {
  name                         = "ca-cat-${var.foundation.app_base}"
  resource_group_name          = var.foundation.resource_group_name
  container_app_environment_id = var.foundation.environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  identity {
    type         = "UserAssigned"
    identity_ids = [var.foundation.pull_identity_id]
  }
  registry {
    server   = var.foundation.acr_login_server
    identity = var.foundation.pull_identity_id
  }
  secret {
    name  = "origin-read"
    value = var.backend_read_token
  }
  secret {
    name  = "origin-write"
    value = var.backend_write_token
  }
  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8000
    transport                  = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  template {
    min_replicas = 1
    max_replicas = 1
    container {
      name   = "catalog-api"
      image  = var.images["catalog-api"]
      cpu    = 0.25
      memory = "0.5Gi"
      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name        = "BACKEND_READ_TOKEN"
        secret_name = "origin-read"
      }
      env {
        name        = "BACKEND_WRITE_TOKEN"
        secret_name = "origin-write"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        failure_count_threshold = 30
        interval_seconds        = 2
      }
    }
  }
  tags = var.foundation.tags
}
resource "azurerm_container_app" "mcp" {
  for_each                     = local.mcps
  name                         = each.value
  resource_group_name          = var.foundation.resource_group_name
  container_app_environment_id = var.foundation.environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  identity {
    type         = "UserAssigned"
    identity_ids = [var.foundation.pull_identity_id]
  }
  registry {
    server   = var.foundation.acr_login_server
    identity = var.foundation.pull_identity_id
  }
  secret {
    name  = "origin-read"
    value = var.backend_read_token
  }
  dynamic "secret" {
    for_each = each.key == "mcp-operations" ? [1] : []
    content {
      name  = "origin-write"
      value = var.backend_write_token
    }
  }
  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8000
    transport                  = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  template {
    min_replicas = var.aca_min_replicas
    max_replicas = var.aca_max_replicas
    http_scale_rule {
      name                = "bounded-http"
      concurrent_requests = "20"
    }
    container {
      name   = each.key
      image  = var.images[each.key]
      cpu    = 0.25
      memory = "0.5Gi"
      env {
        name  = "REQUIRE_AUTH"
        value = "1"
      }
      env {
        name  = "CATALOG_API_URL"
        value = "https://${azurerm_container_app.catalog.ingress[0].fqdn}"
      }
      env {
        name  = "MCP_ALLOWED_HOSTS"
        value = "${each.value}.${var.foundation.environment_domain}:*"
      }
      env {
        name        = "BACKEND_READ_TOKEN"
        secret_name = "origin-read"
      }
      dynamic "env" {
        for_each = each.key == "mcp-operations" ? [1] : []
        content {
          name        = "BACKEND_WRITE_TOKEN"
          secret_name = "origin-write"
        }
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
      liveness_probe {
        transport = "TCP"
        port      = 8000
      }
      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        failure_count_threshold = 30
        interval_seconds        = 2
      }
    }
  }
  tags = var.foundation.tags
}