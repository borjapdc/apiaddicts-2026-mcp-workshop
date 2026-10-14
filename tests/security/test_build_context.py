from pathlib import Path


def test_private_terraform_inputs_are_excluded_from_image_context():
    patterns = set(Path(".dockerignore").read_text().splitlines())
    assert {".local", "**/*.tfvars", "**/*.tfvars.json", "**/*.tfstate*", "**/.terraform", ".env*"} <= patterns
    for service in ["catalog-api", "mcp-catalog", "mcp-operations"]:
        dockerfile = Path(f"src/{service}/Dockerfile").read_text()
        assert "COPY . ." not in dockerfile
        assert "USER 10001" in dockerfile
        assert "--frozen --no-dev" in dockerfile