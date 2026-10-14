var builder = DistributedApplication.CreateBuilder(args);

var catalog = builder.AddDockerfile("catalog-api", "../..", "src/catalog-api/Dockerfile")
    .WithHttpEndpoint(port: 8001, targetPort: 8000, name: "http")
    .WithHttpHealthCheck("/health");

builder.AddDockerfile("mcp-catalog", "../..", "src/mcp-catalog/Dockerfile")
    .WithHttpEndpoint(port: 8002, targetPort: 8000, name: "http")
    .WithReference(catalog.GetEndpoint("http"))
    .WithEnvironment("CATALOG_API_URL", catalog.GetEndpoint("http"))
    .WithEnvironment("MCP_ALLOWED_HOSTS", "host.docker.internal:*,mcp-catalog:*")
    .WithHttpHealthCheck("/health")
    .WaitFor(catalog);

builder.AddDockerfile("mcp-operations", "../..", "src/mcp-operations/Dockerfile")
    .WithHttpEndpoint(port: 8003, targetPort: 8000, name: "http")
    .WithReference(catalog.GetEndpoint("http"))
    .WithEnvironment("CATALOG_API_URL", catalog.GetEndpoint("http"))
    .WithEnvironment("MCP_ALLOWED_HOSTS", "host.docker.internal:*,mcp-operations:*")
    .WithHttpHealthCheck("/health")
    .WaitFor(catalog);

builder.Build().Run();