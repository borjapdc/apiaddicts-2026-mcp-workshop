# Workshop conventions

- Use the root uv.lock, Python MCP official SDK 1.30.0 and shared Dockerfiles. Source: https://github.com/modelcontextprotocol/python-sdk . SDK main v2 API differs.
- MCP must use the SDK initialize/list/call and Streamable HTTP, never manual JSON-RPC substitutes.
- Terraform is the only cloud configuration; Aspire is local only.
- Cloud subscription must be the unique Enabled MVP candidate, explicit tenant/subscription in every provider. Never fall back to Students.
- Never print or commit keys, origin tokens, state, real tfvars or private outputs.
- Read-only and operator tools remain in separate servers/products. Origin ACA requires authentication except health.
- No Foundry/model dependency or deployment without separate explicit authorization.
- Run scripts/tests/test-local.sh and terraform fmt/validate; record runtime PASS/FAIL/BLOCKED, not generated-code success.
- Do not destroy deployed resources during tests. Cleanup requires exact RG/subscription confirmation.
- Consult docs/SOURCE_VALIDATION.md for documented preview discrepancies and docs/EVIDENCE.md for real results.