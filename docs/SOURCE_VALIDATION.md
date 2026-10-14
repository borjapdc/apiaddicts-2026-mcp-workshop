# Validacion documental

Consulta documental ejecutada el 2026-10-12; las pruebas continuaron hasta 2026-10-13 UTC con timestamps reales. Leer una fuente demuestra soporte documental, no despliegue. Los resultados de ejecucion estan en EVIDENCE.md y .local/evidence.json. Terraform utiliza AzureRM 5.9.0, AzAPI 2.13.0; Python usa MCP 1.30.0 de mantenimiento, no la API v2 de main. Aspire AppHost/CLI 13.6.0, .NET 10.0.400.

| FEATURE | SOURCE | VERSION / PREVIEW | VALIDATION |
|---|---|---|---|
| MCP APIM, Developer | https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview | Classic y v2; no workspaces | PASS documental: "Classic tiers: Developer, Basic, Standard, Premium"; availability real consultada con SKUs |
| REST a MCP | https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server | Solo operaciones seleccionadas | PASS documental: "Select one or more API operations"; tools declarados explicitamente |
| MCP nativo | https://learn.microsoft.com/en-us/azure/api-management/expose-existing-mcp-server | MCP 2025-06-18+ | PASS documental: "must conform to MCP version 2025-06-18 or later"; native negocia 2025-11-25 en local |
| Gestion ARM/AzAPI | https://learn.microsoft.com/en-us/azure/api-management/manage-mcp-servers-rest-api | 2025-09-01-preview | PASS: type=mcp; mcpProperties.transportType=streamable; endpoints message uriTemplate=/mcp; tools.operationId ID ARM completo |
| Seguridad MCP | https://learn.microsoft.com/en-us/azure/api-management/secure-mcp-servers | Claves de producto o OAuth | PASS: "Ocp-Apim-Subscription-Key"; productos reader/operator separados; backend keys mediante policies |
| Telemetria MCP | https://learn.microsoft.com/en-us/azure/api-management/monitor-mcp-servers | Dimensiones gen_ai.* | PASS documental; runtime necesita KQL: "doesn't capture the arguments and results" por defecto; no leer context.Response.Body |
| Rate limit | https://learn.microsoft.com/en-us/azure/api-management/rate-limit-by-key-policy | Developer; ventana maxima 300s | PASS: 429; counter-key por Subscription.Id y Api.Id; conteo distribuido no exacto |
| AI Gateway APIM | https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities | Capacidad APIM, no otro recurso | PASS: "it's not a separate offering"; distinguir tokens LLM y llamadas MCP |
| Gateway Foundry | https://learn.microsoft.com/en-us/azure/foundry/configuration/enable-ai-api-management-gateway-portal | Preview; APIM v2 | PASS documental: mismo tenant/subscription; Basic v2 al crear; Developer no elegible para asociar |
| Gobierno tools Foundry | https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/governance | Preview | PASS documental: solo nuevas tools MCP sin managed OAuth; no logs de tool traces en Foundry; policies se aplican en APIM |
| Python MCP ACA | https://learn.microsoft.com/en-us/azure/container-apps/tutorial-mcp-server-python | FastMCP stateless_http=True | PASS: health separado y lifespan/session manager; no usar el almacen en memoria no thread-safe del tutorial como persistencia |
| Hosting ACA | https://learn.microsoft.com/en-us/azure/container-apps/mcp-overview | Standalone, no dynamic sessions | PASS: ingress transport http/auto; no valor ingress="mcp"; replicas min 1 interactivas |
| Auth ACA | https://learn.microsoft.com/en-us/azure/container-apps/mcp-authentication | Entra recomendado | PASS documental; MVP usa compromiso didactico secret ACA/APIM, NO auth integrada Entra ni x-ms-apikey de sessions |
| ACR identity pull | https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull | User-assigned, AcrPull | PASS: ARM audience debe estar permitido; comprobar despues de foundation |
| AddDockerfile | https://aspire.dev/app-host/withdockerfile/ | Aspire 13.6.0 | PASS: context relativo a AppHost; Dockerfile opcional; compilacion y ejecucion reales |
| Aspire ACA | https://learn.microsoft.com/en-us/dotnet/aspire/deployment/azure/aca-deployment | Redirige a aspire.dev | PASS redireccion verificada: https://aspire.dev/integrations/cloud/azure/configure-container-apps/ ; NO usar aspire deploy en este workshop |
| Auth Terraform | https://learn.microsoft.com/en-us/azure/developer/terraform/authenticate-to-azure | CLI, tambien MI/SP segun subguias | PASS: CLI autenticada; providers fijan tenant/subscription, no contexto implicito |
| Seleccion CLI | https://learn.microsoft.com/en-us/azure/developer/terraform/authenticate-to-azure-with-microsoft-account | az account list/set/show | PASS ejecutado: unica MVP Credit Ext; no Azure for Students |
| SDK MCP | https://github.com/modelcontextprotocol/python-sdk | 1.30.0 maintenance; main v2 distinto | PASS firmas inspeccionadas con inspect; initialize/list/call observados por HTTP |
| Pricing | https://azure.microsoft.com/en-us/pricing/details/api-management/ | Precio regional indicativo | PASS consulta: https://prices.azure.com/api/retail/prices ; Developer Sweden Central 0.0658 USD/h, ACR Basic 0.1666 USD/dia |

La URL https://modelcontextprotocol.io/llms-full.txt no pudo extraerse con el lector web; se sustituyo por README oficial y firmas runtime del SDK instalado. Las paginas overview y passthrough no coinciden completamente sobre resources: el taller expone y prueba solo tools, no promete resources/prompts.

## Esquema confirmado

- `Microsoft.ApiManagement/service/apis@2025-09-01-preview`, `properties.type="mcp"`.
- Nativo: serviceUrl base ACA, backend resource con URL completa /mcp, backendId y path=<servidor>/mcp. Learn muestra endpoints array, pero ARM real exige diccionario: endpoints.message.uriTemplate=/mcp. schema_validation_enabled=false solo en passthrough; initialize/list/call y drift ya probados. Sin backendId esta instancia devolvia tools vacias. URL publica nativa = gateway_url + properties.path, sin sumar otro /mcp. Workaround preview observado, no contrato estable universal.
- REST-backed: API MCP separada mas `service/apis/tools` con `operationId` de cada operacion real importada. No tools de mutacion en la fachada REST.
- Policies: service/apis/policies, nombre policy. APIM devuelve format=xml y normaliza tabs/CRLF; XmlWriter conserva representacion sin ignore_changes. Variante REST-MCP conserva key para REST interna, que la elimina antes de ACA.
- Productos: relacion service/products/apis gestionada por azurerm_api_management_product_api: GET singleton preview devolvio 405 en AzAPI. Reader/operator probados, anonimo/reader-write 401 y operator demo-pending.
- Endpoints nativos derivan de path retornado por ARM. REST-backed usa sufijo documentado /mcp. Ambos probados por SDK real a traves del gateway.
- AzureRM no dispone de recurso MCP nativo segun Learn consultado. La validacion local de provider no prueba disponibilidad del gateway runtime.

## Fuentes complementarias

- https://registry.terraform.io/providers/hashicorp/azurerm/5.9.0/docs
- https://registry.terraform.io/providers/Azure/azapi/2.13.0/docs/resources/resource
- https://aspire.dev/get-started/install-cli/ : instalacion NuGet oficial, version 13.6.0 probada.
- https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits : verificar limites ACR; la consulta regional ACR usages intento una ruta invalida y devolvio 404, no se interpreto como falta de cuota.
- https://raw.githubusercontent.com/Azure-Samples/AI-Gateway/main/modules/apim-streamable-mcp/api.bicep : ejemplo oficial con backend URL completa /mcp y backendId. El taller mantiene management API 2025-09-01-preview, no adopta la version anterior del sample.
- https://learn.microsoft.com/en-us/rest/api/apimanagement/api/create-or-update?view=rest-apimanagement-2025-09-01-preview y https://learn.microsoft.com/en-us/azure/templates/microsoft.apimanagement/2025-09-01-preview/service/apis : tambien muestran array, discrepancia runtime registrada.

## Telemetria observada

KQL real devuelve api.type=mcp-backend, network.protocol.name=MCP, gen_ai.operation.name=tools/call, gen_ai.tool.name, user_agent.name/version, auth.type y DurationMs. No aparece necesariamente api.type=Mcp de Learn. Consultas filtran network.protocol.name para ambas formas. Sesion vacia es coherente con stateless. Hay filas reales get_service/create_access_request, incluidos errores anteriores; no se borran ni simulan para embellecer la demo.