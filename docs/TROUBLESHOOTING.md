# Resolucion por sintomas

Todos los comandos parten de root del repositorio. No poner keys en URLs/logs. Exit 0 exito, exit 1 tests/cliente fallidos, exit 2 gate BLOCKED.

| Sintoma | Comprobacion y accion |
|---|---|
| 401 APIM | Key ausente/invalida; obtener con listSecrets y usar variable. tools/list requiere auth tambien. |
| 403 | Producto/rol incorrecto o policy; reader no es operator. No ampliar reader para arreglar la demo. |
| 401 ACA | Correcto si no se presenta secreto origen. Para diagnostico usar test-backends; no desactivar auth cloud. |
| 404 | URL/operationId no real; outputs gateway_endpoints, path y suffix /mcp. REST tiene prefix /catalog mas /api/services. |
| 421 | SDK Host allowlist: HTTPS omite :443; incluir FQDN exacto. Hay test de regresion. |
| 429 | Rate limit por producto/API, no por IP. Initialize tambien puede consumir ventana. Ejecutar govern; esperar la ventana en el test. |
| 500/502 | Backend timeout, Host o policy; /health, ACA runningStatus y test-backends. No inventar datos fallback. |
| MCP session | Stateless no necesita persistir session ID. No usar sesiones antiguas entre revisiones. |
| Invalid JSON-RPC | No enviar REST a /mcp; SDK oficial initialize seguido de tools/list/call; Accept y Content-Type los gestiona SDK. |
| ReadTimeout tras revision | Smoke read-only tiene cuatro intentos acotados. Repetir test-backends; no reintentar mutacion ciegamente. |
| Region/SKU no disponible | Preflight usa SKUs reales de MVP; editar region y probar coste antes de apply. Nunca seleccionar Students. |
| ACR auth failure | AcrPull identity al registry, admin=false, `az acr config authentication-as-arm show`; tres digests reales. |
| Terraform lock | No force-unlock mientras exista un apply; confirmar propietario/proceso y preservar state. |
| AzAPI endpoints array 400 | Se observo discrepancia preview: ARM exige diccionario; ver SOURCE_VALIDATION. No cambiar version sin verificar schema/runtime. |
| API tools ;rev=1 400 | Usar ID canonico /apis/catalog-rest/operations/<operation>, no ID revision devuelto por AzureRM. |
| 412 ETag tools | If-Match=* y locks por APIM, no tools paralelas sin serializacion. |
| Product API GET 405 | Relacion PUT es valida pero singleton preview no legible; usar recurso AzureRM product_api. |
| 409 ManagementApiRequestFailed | Developer puede tener downtime de administracion/plataforma. Preservar state y reanudar deploy, no recrear ni upgrade automatico. |
| XML drift | APIM reformatea XML; inspeccionar plan y equivalencia. No ignorar policy security changes. |
| Aspire falla con HTTP | Perfil local ASPIRE_ALLOW_UNSECURED_TRANSPORT=true. Nunca extender ese flag a cloud. |
| Aspire CLI no encontrada | `dotnet tool install -g Aspire.Cli --version 13.6.0`, PATH tools o .local/tools. |
| Docker runtime | `docker info`; permisos usuario o servicio daemon. No usar sudo interactivo desde agente. |
| Permisos Azure/tenant | BLOCKED; az account show/list, permisos de providers/RBAC. No reautenticar con otra suscripcion. MFA debe resolverse directamente en terminal. |
| Sin telemetria | Ingesta asincroma/cap 0.1GB; observe no marca PASS sin gen_ai.tool.name real. Consultar AppRequests o requests en contexto correcto. |

## Diagnostico declarativo

```bash
terraform -chdir=infra/terraform/foundation validate
terraform -chdir=infra/terraform/workload plan -input=false
terraform -chdir=infra/terraform/gateway plan -input=false
./scripts/tests/test-backends.sh
./scripts/tests/test-azure.sh
./scripts/demo/observe.sh
```

Para logs ACA usar `az containerapp logs show` solo con nombres y RG de outputs. No mostrar env/secrets. Un health 200 no prueba protocolo; un recurso MCP creado no prueba policies, herramientas ni observabilidad.