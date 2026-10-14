# Costes y limpieza responsable

Consulta retail real: 2026-10-12, Sweden Central, USD, sin impuestos ni descuentos MVP. Endpoint https://prices.azure.com/api/retail/prices y pricing https://azure.microsoft.com/en-us/pricing/details/api-management/ . Otros costes: https://azure.microsoft.com/en-us/pricing/details/container-registry/ , https://azure.microsoft.com/en-us/pricing/details/container-apps/ , https://azure.microsoft.com/en-us/pricing/details/monitor/ . Usar https://azure.microsoft.com/en-us/pricing/calculator/ para la oferta concreta.

| Medidor observado | Tarifa retail |
|---|---|
| APIM Developer Unit | 0.0658 USD/h |
| ACR Basic Registry Unit | 0.1666 USD/dia |
| ACA Standard vCPU Active Usage | 0.000024 USD/vCPU segundo |
| ACA Standard Memory Active Usage | 0.000003 USD/GiB segundo |
| Analytics Logs ingestion | 2.99 USD/GB |

Estimacion indicativa compute/ingesta: 5.2848 USD/dia usando cinco replicas (0.25 vCPU/0.5GiB), Developer una unidad, ACR Basic y 0.1GB logs/dia. No es presupuesto duro ni total garantizado: excluye solicitudes, egress, builds ACR, exceso storage, impuestos, tolerancias del cap diario y cualquier servicio opcional. Preflight bloquea si esos medidores exceden el gate de 6 USD/dia; renovar consulta al cambiar region o fecha. Existe coste minimo mientras APIM/ACR existen, incluso sin clientes. Los creditos MVP no significan gratuidad.

Retail Prices devolvio 429 durante la repeticion final. El script puede reutilizar solo una consulta oficial verificada de la misma region y moneda, con cinco medidores completos y antiguedad maxima seis horas. Emite WARN con edad y conserva checked_at_utc; region distinta o cache caducada fuerza consulta nueva y, si falla, BLOCKED. Eliminar .local/costs.json fuerza refresh. No se inventan precios ni se extiende indefinidamente su vigencia.

Logs cap 0.1GB/dia puede suspender ingesta e impedir OBS-01. Tags ttl informativos no borran nada. Min 0 en MCP reduce idle/cold start, pero catalogo sigue en 1 y APIM continua facturando. No hay opcion de apagar APIM Developer que equivalga a borrar.

## Scope real

Solo RG rg-apiaddicts-mcp-demo-mvp-workshop-01-b64n92, instancia persistida b64n92, suscripcion MVP Credit Ext 1177bd9a-...-3813 y tenant c149c7b9-...-be67. Nunca eliminar recursos de otros grupos. No perder los tres states: son la prueba de propiedad y dependencias. Guardarlos cifrados con controles de acceso antes de borrar el directorio.

## Plan no destructivo

```bash
./scripts/terraform/assert-subscription.sh
./scripts/terraform/destroy.sh --what-if
terraform -chdir=infra/terraform/gateway state list
terraform -chdir=infra/terraform/workload state list
terraform -chdir=infra/terraform/foundation state list
```

```powershell
./scripts/terraform/assert-subscription.ps1
./scripts/terraform/destroy.ps1 -WhatIf
```

Se exige tag workshop_instance_id correcto y se valida el scope de cada plan. Orden inverso: gateway (tools antes de operaciones REST), workload, foundation. Los tests NUNCA ejecutan destroy. Si alguno de los planes falla por APIM management downtime, no proceder parcialmente sin revisar el siguiente estado.

## Destructivo, solo tras aprobacion

```bash
TARGET=$(terraform -chdir=infra/terraform/foundation output -json foundation)
RG=$(printf '%s' "$TARGET" | jq -r .resource_group_name)
SUB=$(printf '%s' "$TARGET" | jq -r .subscription_id)
./scripts/terraform/destroy.sh --apply --confirm-group "$RG" --confirm-subscription "$SUB"
az group exists --name "$RG" --subscription "$SUB"
az apim list --subscription "$SUB" --query "[?resourceGroup=='$RG'].name" -o json
```

```powershell
$target = terraform -chdir=infra/terraform/foundation output -json foundation | ConvertFrom-Json
./scripts/terraform/destroy.ps1 -Apply -ConfirmGroup $target.resource_group_name -ConfirmSubscription $target.subscription_id
az group exists --name $target.resource_group_name --subscription $target.subscription_id
```

Esperar RG exists=false y APIM list sin la instancia. Revisar Cost Management filtrado por RG tras latencia de facturacion; no declarar cargos terminados por cerrar el dashboard o por quitar un producto. Se eliminan logs/App Insights con foundation; exportar solo evidencia no sensible antes. No se ha autorizado destruir los recursos recien creados durante esta ejecucion.

Backend local solo para taller personal. Para equipos: crear backend Azure Blob aparte aprobado con cifrado, RBAC y locking; migrar cada root con `terraform init -migrate-state`; usar key de state distinta por instancia y modulo. Un nuevo participante necesita nuevo RG y state, no editar instance sobre el state existente.