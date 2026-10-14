# Guion APIAddicts 2026: 45 minutos

Narrativa unica: descubrir -> gobernar -> observar y limitar. Todos los comandos desde root. Infraestructura debe estar desplegada antes de la charla: APIM Developer tardo unos 30 minutos en el primer provisioning y tuvo downtime de administracion. No ejecutar apply en los 45 minutos salvo un plan-only ilustrativo.

La salida predeterminada es visual: tablas, fases con duracion, estados coloreados y cuenta atras en esperas de rate limit. Para proyectar, usar terminal interactiva; para diagnostico detallado anadir --json en Bash o -Json a demo.ps1. No es un unico JSON agregado: cada llamada guarda su payload validado y redactado en .local/demo-results/*.json. Un 429 previsto se presenta como WARN, mientras que un error inesperado conserva FAIL/BLOCKED y salida no cero.

Los comandos de la charla estan en scripts/demo; infraestructura en scripts/terraform, verificaciones en scripts/tests y configuracion/evidencia en scripts/tools. El motor interno compartido esta en scripts/lib. Todas las rutas de este guion parten de la raiz del repositorio.

## Preparacion anterior

```bash
./scripts/terraform/preflight.sh
./scripts/demo/local.sh
```

Segunda terminal:

```bash
./scripts/tests/test-local.sh --smoke
./scripts/tools/configure-mcp.sh
./scripts/tests/test-backends.sh
./scripts/tests/test-azure.sh
./scripts/demo/observe.sh
```

PowerShell: mismos nombres .ps1, `-Smoke` en test-local. Revisar EVIDENCE: un BLOCKED debe explicarse antes de mostrar la capacidad. No capturar claves ni abrir tfvars/state en proyector. Dataset read-only estable; creacion de solicitud ficticia deduplicada. Estado efimero se resetea con revision/reinicio del catalogo; no hacerlo durante pruebas.

## 0-15: Demo 1, descubrir

```bash
./scripts/demo/demo.sh --step discover
curl --fail http://localhost:8001/openapi.json
```

```powershell
./scripts/demo/demo.ps1 -Step discover
Invoke-RestMethod http://localhost:8001/openapi.json
```

0-4: diagrama y tres contenedores en http://localhost:15888. Mostrar health 200 y banner HTTP local. Que: negocio en catalog-api; como: contenedores orquestados por Aspire, misma imagen que cloud; por que: readiness y composicion local.

4-9: el comando ejecuta initialize, tools/list, search_services(payments), get_service_contract(orders) y tools/list operaciones. Esperar 4 tools lectoras y 2 de operaciones, protocolo 2025-06-18+ (local observado 2025-11-25). Search devuelve propietario ficticio y SLA claramente demo.

9-15: OpenAPI real y contrato ilustrativo. MCP añade descubrimiento, schemas/annotations, transporte y lifecycle; no aporta aprobacion empresarial ni requiere un LLM para llamar tools. Pregunta al publico: donde deberia vivir el control de acceso cuando el cliente puede descubrir varias herramientas?

Plan B: captura local real guardada en docs/aspire-dashboard.png, snapshots en docs/fixtures/local-tools-8002.json y local-tools-8003.json cuando publish_evidence los haya generado. Estos archivos se excluyen de Git y deben prepararse en cada maquina. Son snapshots de ejecucion local, NO cloud ni metricas reales de Azure. Si Docker no esta disponible, tres comandos uvicorn de README y tests de protocolo por subprocess; LOCAL-01 seguiria BLOCKED.

## 15-31: Demo 2, gobernar

```bash
./scripts/demo/demo.sh --step cloud
./scripts/tests/test-azure.sh
./scripts/tests/test-backends.sh
terraform -chdir=infra/terraform/gateway output -json tool_operation_ids
```

```powershell
./scripts/demo/demo.ps1 -Step cloud
./scripts/tests/test-azure.ps1
./scripts/tests/test-backends.ps1
terraform -chdir=infra/terraform/gateway output -json tool_operation_ids
```

15-18: Portal RG/ACR/ACA: las tres imagenes son digests, pull identity AcrPull, no admin password. Outputs foundation contienen IDs de enlaces portal; no reconstruir hostnames.

18-25: tools/list por APIM nativo y REST-backed. Esperar mismas cuatro tools de lectura pero schemas/annotations no necesariamente identicos: Python decide el contrato nativo, APIM decide tools REST-backed. Mostrar tool mappings a /apis/catalog-rest/operations/<id>, no afirmar conversion automatica de toda la API. get_service(payments) debe representar el mismo servicio en ambos.

25-31: test-azure exige rechazo anonimo, rechazo reader al servidor operator y creacion por operator. test-backends exige ACA sin token origen 401, health 200, initialize/list autenticados. El secreto compartido de origen es compromiso didactico, no red privada. Pregunta: por que una URL ACA publica no deja de ser un bypass por poner APIM delante?

El test deja entre fases una ventana de rate limit para no contaminar resultados. No repetir tools/list compulsivamente justo antes del bloque 3. Keys se capturan en memoria, no aparecen en salida. La tool evaluate_access_request devuelve approved=false, nunca aprobacion real.

Plan B: demo discover y explicar BLOQUEO cloud exacto en EVIDENCE. No presentar snapshots locales como APIM live. Si hay downtime Developer, conservar state; no cambiar tenant, suscripcion ni SKU para salvar la charla.

## 31-42: Demo 3, observar y limitar

```bash
./scripts/demo/demo.sh --step govern
./scripts/demo/observe.sh
```

```powershell
./scripts/demo/demo.ps1 -Step govern
./scripts/demo/observe.ps1
```

31-35: carga acotada (12 sesiones como maximo, presupuesto de burst calculado del limite y maximo 25 respuestas, mas recovery, presupuesto total 30). Concurrencia 1; sin mutaciones. Esperar algunos 200/202, un 429 y exito tras ventana de 30s. Counter key usa Subscription.Id + Api.Id, no IP compartida. El contador distribuido no es perfectamente exacto. initialize/list tambien pueden consumir limite. Se miden tanto el exito inicial como recovery; pocas muestras no constituyen benchmark.

35-39: medicion wall-clock initialize+tools/call, p50/p95 de exitos unicamente y sample count. Una sola muestra no es un percentil estadisticamente defendible: decirlo. Umbral 1500ms indicativo, no SLA/TPS. Escala/retry/cold start y limites son el discurso de rendimiento, no un numero de throughput prometido.

39-42: Azure Monitor Logs, workspace del output log_workspace_guid. KQL principal tambien ejecutado por observe:

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| where Properties["network.protocol.name"] == "MCP"
| where Properties["gen_ai.operation.name"] == "tools/call"
| project TimeGenerated, tool=tostring(Properties["gen_ai.tool.name"]),
          session=tostring(Properties["gen_ai.conversation.id"]),
          durationMs=DurationMs, ResultCode, Success, OperationId
| order by TimeGenerated desc
| take 20
```

Volumen, error ratio, p50/p95 por herramienta:

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| where Properties["network.protocol.name"] == "MCP"
| where Properties["gen_ai.operation.name"] == "tools/call"
| summarize calls=count(), failures=countif(Success == false),
            p50_ms=percentile(DurationMs,50), p95_ms=percentile(DurationMs,95)
  by tool=tostring(Properties["gen_ai.tool.name"])
| extend errorRatio=todouble(failures)/calls
```

En App Insights clasico usar queries/appinsights.kql: tabla requests, timestamp, customDimensions, duration. No mezclar esos nombres con AppRequests. Para buscar correlacion si formato MCP difiere:

```kusto
AppRequests
| where TimeGenerated > ago(1h)
| project TimeGenerated, Name, ResultCode, DurationMs, OperationId, Properties
| take 20
```

No mostrar argumentos/resultados ni headers de auth. ApiManagementGatewayLogs aporta evidencia gateway si se configura resource-specific logs, pero no sustituye una tool trace no observada. Un query valido sin filas es BLOCKED, no PASS. Si ingestion se retrasa, repetir observe tras trabajo posterior; no inventar valores. Pregunta: diferencia entre limitar llamadas MCP y limitar tokens de un modelo?

Plan B: salida guardada .local/evidence.json de GOV-LOAD, con timestamp y entorno, y snapshot de observabilidad solo si existieron filas reales. En ausencia, exponer OBS-01 BLOCKED y mostrar KQL como procedimiento pendiente, no captura live simulada.

## 42-45: Foundry, extension opcional

```bash
./scripts/demo/demo.sh --step foundry
```

```powershell
./scripts/demo/demo.ps1 -Step foundry
```

AI Gateway es APIM. Integracion Foundry preview: APIM v2, mismo tenant/suscripcion, permisos y networking. Developer principal NO elegible para asociacion. Tokens/TPM por proyecto/modelo son otro contador. Solo nuevas tools MCP elegibles sin managed OAuth se median segun guia vigente; no afirmar retroactividad ni tool traces Foundry. Ver FOUNDRY_OPTIONAL para requisitos/documentacion, no ejecutar despliegue costoso de modelos durante charla.

Cerrar con limites reales, evidencia y cleanup. No borrar infra durante charla. Entregar README + tres states protegidos al propietario; no copiar secretos a slides.