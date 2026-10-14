# Seguridad

## Fronteras y pruebas

| Frontera | Control efectivo | Prueba |
|---|---|---|
| Cliente -> APIM | Subscription keys scoped a producto, subscriptionRequired=true | test-azure: anonimo 401/403, valido initialize/list/call |
| Reader -> operaciones | Producto operator diferente y policy Product.Id | test-azure: reader rechazado, operador crea demo-pending |
| Gateway -> ACA | x-backend-token sobrescrito con named value secret | test-backends: URL publica sin secreto devuelve 401 |
| MCP read -> REST POST | MCP read sin write secret; catalogo POST solo write | pytest origin_scope y test_catalog |
| HTTP cloud | Ingress allow_insecure_connections=false | Terraform + verificacion ACA |
| ACR pull | User-assigned MI, AcrPull solo en registry, admin=false | az containerapp list y az acr config authentication-as-arm show |

Las subscription keys son credenciales de portador, no identidades humanas ni RBAC Entra. Cualquier persona que posea la key operator puede mutar datos ficticios. No hay aprobacion empresarial ni autenticacion de usuarios finales.

## Secretos

Terraform state contiene secretos aunque outputs sean sensitive. .tfstate, tfvars reales, linked.auto.tfvars.json, detected.auto.tfvars.json, .terraform, .env.local, .local y .vscode/mcp.json estan ignorados. Unix usa 0600 para archivos privados; en Windows aplicar ACL de usuario a la carpeta de trabajo. No publicar logs/state. Claves se consultan con listSecrets y se asignan a variables, nunca se imprimen. No subirlas a prompts, capturas, historial ni repositorio.

MVP usa ACA secrets y APIM secret named values. Es un compromiso didactico, NO Key Vault, OAuth ni origen privado. Endurecimiento: Key Vault con MI y rotacion; APIM con conectividad privada a ACA; OAuth 2.1 con Entra, audiences y scopes separados; validar issuer/claims; workload identity federada para CI; RBAC a scope RG/registry, no permisos amplios permanentes.

## Logs y streaming

Se registran metadatos de request/API/correlacion, nunca bodies en APIM. Frontend/backend request/response bytes=0 y no se listan headers sensibles. No acceder a context.Response.Body: rompe streaming. No incluir tool arguments/results en trace. Activar payload logging solo conscientemente para dataset ficticio, en scope especifico, revalidar streaming y apagar despues mediante Terraform; no hay flag de captura habilitado en este MVP.

Health publico es una excepcion para probes; no constituye bypass al catalogo. Local REQUIRE_AUTH=0 solo se usa en localhost/Aspire. Dashboard HTTP local no se debe exponer ni publicar con un tunel. El banner unsecured de la captura describe esta limitacion real.

## Amenazas

Input validation no elimina prompt injection/tool poisoning. Tratar descripciones, contratos y resultados como datos no confiables; allowlist de herramientas/servidores, revisiones de cambios de schemas, aprobacion humana de acciones sensibles, permisos minimos, restricciones de egress y limites de contenido. Evitar encadenar credenciales o ejecutar texto de herramientas como codigo. Maximos de query/limit/purpose y IDs tipados no sustituyen controles de autorizacion.

No hay CORS wildcard cloud: CLI y VS Code desktop no requieren CORS. Navegadores necesitan un allowlist explicito revisado antes de ampliar alcance. El despliegue no registra aplicaciones Entra ni concede permisos de tenant.