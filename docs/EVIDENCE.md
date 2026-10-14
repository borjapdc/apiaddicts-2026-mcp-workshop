# Evidencia de ejecucion

Fuentes verificadas el 2026-10-12. Ejecucion local/Azure iniciada ese dia y continuada el 2026-10-13 UTC; timestamps completos se conservan localmente en docs/evidence/run.json. No son resultados simulados. En aquella fecha el repositorio no estaba publicado.

Las evidencias JSON/XML, fixtures y captura del dashboard se excluyen del repositorio publico. Esta pagina resume comprobaciones historicas del autor, no certifica un nuevo clon ni el estado actual de Azure. Cada participante debe ejecutar las validaciones y generar sus propios artefactos locales.

## Objetivo observado

- Suscripcion unica autorizada: **MVP Credit Ext**, `1177bd9a-...-3813`.
- Tenant: `c149c7b9-...-be67`; region `swedencentral`.
- RG nuevo: `rg-apiaddicts-mcp-demo-mvp-workshop-01-b64n92`.
- APIM Developer: `apim-apiaddicts-mcp-demo-mvp-workshop-01-b64n92`.
- ACR Basic: `acrapiaddictsmcpdemomvpworkshop01b64n92`.
- `az containerapp env list-usages` observado: Consumption usage=0.75 cores, limit=100; maximo configurado del workshop 1.25 cores. Capacidad regional de entornos tambien comprobada en preflight.
- No Foundry, modelos, recursos de otra suscripcion ni borrado de recursos recien creados.

IDs ARM y endpoints sin claves se conservan localmente en docs/evidence/endpoints.json. State/tfvars/secrets solo en archivos privados ignorados. No publicar .local completa ni los logs de troubleshooting sin revision.

## Aceptacion

| Criterio | Estado | Comando ejecutado / evidencia observada |
|---|---|---|
| LOCAL-01 | PASS | Aspire CLI 13.6.0 run --apphost aspire/AppHost/AppHost.csproj; tres Docker containers healthy; /health 200 puertos 8001/2/3; dashboard 15888 200; captura real conservada localmente |
| LOCAL-02 | PASS | scripts/tests/test-local.ps1 -Smoke y test-local.sh --smoke; SDK initialize/list/call de ambos MCP, cuatro/dos tools; protocolo 2025-11-25; pytest por red |
| BUILD-01 | PASS | docker build de tres Dockerfiles y smoke Aspire; USER 10001; COPY negativo de linked.auto.tfvars.json falla por .dockerignore; sin secretos embebidos |
| TF-01 | PASS | terraform fmt -check -recursive infra/terraform y validate en foundation/workload/gateway, providers/locks reales |
| TF-02 | PASS | deploy --what-if y planes de stages; suscripcion/tenant MVP explicitos, random sufijo persistido, RG nuevo; scope_plan rechaza IDs ajenos/reemplazos |
| AZ-01 | PASS | ACR builds/digests, tres ACA Succeeded/Running; user-assigned pull identity en registry y AcrPull; az acr config authentication-as-arm show -> enabled |
| AZ-02 | PASS | APIs mcp nativas dos y REST-backed una; cuatro tools canonicamente vinculadas; test-azure devuelve 4/4/2 tools y get_service(payments) equivalente |
| SEC-01 | PASS | test-azure: anonimo 401; product keys validas inicializan/listan/invocan; REST reader tambien 200 |
| SEC-02 | PASS | reader en mcp-operations rechazado 401; operator create_access_request -> demo-pending; separacion servidor/producto y backend write token |
| SEC-03 | PASS | test-backends: las tres URL ACA rechazan acceso anonimo a /api/services o /mcp con 401; health publico 200; MCP directo con token origen funciona |
| GOV-01 | PASS | scripts/demo/load.sh: burst 11 respuestas HTTP (200,202,429), tras ventana tools/call exitoso; concurrencia 1 y presupuesto total 30 |
| OBS-01 | PASS | scripts/demo/observe.sh consulta AppRequests; gen_ai.tool.name real get_service/create_access_request, DurationMs, ResultCode y OperationId. api.type observado mcp-backend, no Mcp; KQL adaptada a network.protocol.name=MCP |
| REP-01 | BLOCKED | deploy --apply repetido end-to-end y tres planes exit 0. Copia limpia sin privados/venv: 19 tests, lint/tipos y AppHost build. Clone remoto limpio no probado porque no hay commit/remoto publicado; no equivale a clone/deploy de un tercero. Windows nativo/CI remoto no ejecutados |
| CLEAN-01 | PASS | scripts/terraform/destroy.sh --what-if: tres planes inversos y scope/tag verificados, applied=false. No se ejecuto destruccion |
| DOC-01 | PASS | Veinte fuentes oficiales consultadas, versiones y preview registrados en SOURCE_VALIDATION; archivos/checks del guion presentes; discrepancias documentadas, no ocultadas |

## Resultados reproducibles

```bash
./scripts/tests/test-local.sh --smoke
./scripts/tests/test-backends.sh
./scripts/tests/test-azure.sh
./scripts/demo/load.sh
./scripts/demo/observe.sh
terraform -chdir=infra/terraform/foundation plan -detailed-exitcode
terraform -chdir=infra/terraform/workload plan -detailed-exitcode
terraform -chdir=infra/terraform/gateway plan -detailed-exitcode
./scripts/terraform/destroy.sh --what-if
uv run python -m scripts.tools.publish_evidence
```

PowerShell equivalentes existen y se han ejecutado con PowerShell 7.6.3 en Linux. No implica prueba en Windows. docs/evidence/pytest.xml recoge pruebas ejecutadas localmente; en la fecha de esta evidencia historica aun no existia una ejecucion CI remota. Los snapshots de lector y operaciones en docs/fixtures son ejecuciones locales etiquetadas, no trazas cloud.

## Rendimiento y observabilidad

Ultima carga observada: p50 933.79ms / p95 1035.40ms de **dos** exitos, initialize+tools/call wall-clock, concurrencia 1. Muestra demasiado pequena para afirmar capacidad/TPS o SLA. Umbral 1500ms indicativo. Gateway tool durations reales son otra medicion; no comparar sus percentiles con wall-clock CLI sin explicar el alcance.

Filas reales incluyen create_access_request 200 en 138.54ms y get_service 200 en 19.18-118.87ms en consultas de esta ejecucion. Tambien conservan errores 404 previos a corregir path; no se limpian para aparentar exito. Session ID vacio por stateless. Payload logging bytes=0; no se habilitaron argumentos/resultados para obtener observabilidad.

## Incidencias resueltas y reservas

1. AzureRM 5 requiere logs_destination=log-analytics explicito para ACA workspace.
2. Host SDK: fqdn:* no admite fqdn sin puerto; ahora ambos, manteniendo DNS rebinding protection.
3. Tool operationId no acepta ;rev=1; se usa ID canonico y If-Match=* con locks.
4. Learn describe endpoints array; ARM real exige diccionario. Passthrough requiere backendId de backend /mcp; URL publica es path completo. Exception schema se limita a native y esta probada.
5. Binding AzAPI PUT/GET no refrescable (GET 405); recurso AzureRM product_api lo gestiona.
6. Developer tuvo 409 de endpoint administracion temporal; se reanudo mismo state sin cambiar SKU/suscripcion.
7. APIM normaliza XML format=xml/tabs/CRLF; XmlWriter/gitattributes eliminan drift sin ignore_changes.
8. REST-backed necesita key en salto APIM interno; la fachada REST la elimina antes de ACA. Test real de equivalencia detecto el 401 oculto en content pese a isError=false.
9. Learn api.type=Mcp no coincide con runtime mcp-backend; KQL usa dimension MCP observada. OBS estuvo BLOCKED y solo cambio a PASS despues de consulta con filas reales.

Reservas: SQLite efimera de una replica; backend shared secrets didacticos; Developer sin SLA; preview ARM requiere revalidacion en otra instancia/fecha. Alias streamablehttp_client y TestClient httpx emiten avisos de deprecacion, no fallos. Foundry opcional solo documentado. No afirmar certeza 100% ni produccion lista.

Retail Prices devolvio 429; repeticion final uso cache oficial regional reciente (WARN, antiguedad registrada) y completo las tres etapas sin drift. Hay test de expiracion y region; no reusar tarifas viejas indefinidamente. Fuente limpia local en .local/clean-checkout se obtuvo con git ls-files/tar sin commit ni copiar state/secretos; sus tests no aplican otra infraestructura.

## Costes y limpieza

Recursos siguen creados y pueden generar cargos. Estimacion retail indicativa 5.2848 USD/dia compute/ingesta, no total garantizado. APIM Developer factura incluso sin trafico; TTL no borra. [Cleanup](COSTS_AND_CLEANUP.md) exige --apply y confirmacion exacta de RG/subscription, orden gateway/workload/foundation. Destruccion no autorizada ni ejecutada en esta sesion.

## Visualizacion de scripts

Los comandos reproducibles de esta guia usan las rutas reorganizadas por responsabilidad (demo/terraform/tests/tools/lib). Los artefactos JSON historicos conservan los comandos que se ejecutaron en su fecha, incluidas rutas planas anteriores; reorganizarlos no implica volver a desplegar ni reprobar recursos Azure.

Reorganizacion verificada el 2026-10-14: 49 tests pasan, lint/tipos y smoke local correctos. Todos los wrappers Bash se comprobaron desde un directorio externo; PowerShell 7.6.3 en Linux valido ayuda/sintaxis y credenciales con CLI simuladas, sin leer secretos reales. scripts/demo/demo.sh --step discover funciono contra Aspire. No se ejecutaron apply, destroy ni mutaciones Azure en esta reorganizacion.

Verificada el 2026-10-13: demo discover y cloud presentan tablas reales, protocolos y duracion por llamada. Bash --json y PowerShell -Json produjeron cuatro objetos SDK parseables, incluidas cadenas largas sin cortes. Las esperas interactivas muestran barra/cuenta atras; al redirigir salida conservan el aviso de 31s y omiten animaciones.

Demo govern ejecutada con once respuestas de burst: cuatro HTTP 200, un 202 y seis 429; recuperacion tools/call exitosa tras ventana. Los 429 aparecen como WARN sin traceback. El SDK puede cerrar el stream con BrokenResourceError: solo se considera esperado con evidencia 429 del mismo intento y sin otro HTTP de error. Hay regresiones para errores mixtos y 500 posterior a 429, que siguen fallando.

Las latencias mostradas son mediciones reales, no mejoras prometidas: en esta comprobacion p50=1209.26ms y p95=1611.72ms sobre dos exitos. KQL devolvio filas de get_service/create_access_request en tabla. Los resultados SDK redactados se guardan en .local/demo-results; logs visuales locales en .local/presentation-{local,cloud,govern}.log, ignorados por Git. Esta mejora no aplica Terraform ni ejecuta mutaciones cloud.