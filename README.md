# change-bridge

ArgoCD (Akuity) → ServiceNow change request bridge. Polls the Akuity API for
production sync operations and drives the CR lifecycle (create → start →
close → attach audit) against the existing ServiceNow CR API.

See [docs/project-context.md](docs/project-context.md) for architecture,
conventions, and constraints, and [docs/EVENT-BRIDGE-DESIGN.md](docs/EVENT-BRIDGE-DESIGN.md)
for the full design.

## Quick start

```bash
uv sync
cp .env.example .env
docker run -d --name bridge-redis -p 6379:6379 redis:7-alpine
uv run python -m bridge
```

## Development

```bash
make check   # lint + typecheck + test
```

See [docs/local-development.md](docs/local-development.md) for the mock-server
workflow.
