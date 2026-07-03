# Project Context

## Purpose
The Network Egress Checker is a lightweight, self-service tool for tenants on a shared AKS cluster managed via ArgoCD. It generates synthetic network traffic to user-defined egress endpoints and exposes results as Prometheus metrics and structured container logs. The platform engineering team owns the checker application; tenant teams only provide a ConfigMap declaring which endpoints to check.

## Tech Stack

| Component              | Technology                                    |
|------------------------|-----------------------------------------------|
| Language               | Python 3.14+                                  |
| Package Manager        | uv                                            |
| Async Runtime          | asyncio (stdlib)                              |
| HTTP Client            | httpx (async)                                 |
| Configuration Parsing  | pydantic v2, pyyaml                           |
| Metrics                | prometheus_client                             |
| Logging                | structlog (JSON output)                       |
| Kubernetes Client      | kubernetes (official Python client)           |
| Linting & Formatting   | Ruff                                          |
| Type Checking          | mypy (strict mode)                            |
| Testing                | pytest, pytest-asyncio, pytest-cov            |
| Container Base Image   | python:3.14-slim (multi-stage build)          |
| Kubernetes Manifests   | Kustomize (hydrated for ArgoCD)               |
| GitOps                 | ArgoCD                                        |
| Observability          | Azure Managed Prometheus, Grafana             |

## Project Structure

```
network-egress-checker/
├── src/
│   └── egress_checker/          # Main application package
│       ├── __init__.py
│       ├── __main__.py          # Entrypoint
│       ├── config.py            # Pydantic models, YAML loader
│       ├── checks/              # Check implementations
│       │   ├── __init__.py
│       │   ├── http.py          # HTTP/HTTPS checker
│       │   └── tcp.py           # TCP checker
│       ├── diagnostics.py       # Failure classification, suggested actions
│       ├── metrics.py           # Prometheus metric definitions
│       ├── logging.py           # structlog configuration, JSON formatter
│       ├── health.py            # /healthz and /readyz server
│       └── scheduler.py         # Async check scheduler with bounded concurrency
├── tests/
│   ├── conftest.py
│   ├── unit/                    # Fast, isolated unit tests
│   └── integration/             # Tests requiring running app or network
├── kustomize/
│   ├── base/                    # Platform-owned base manifests
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── podmonitor.yaml
│   └── overlays/
│       └── example/             # Example tenant overlay
├── .devcontainer/
│   └── devcontainer.json        # Dev container configuration
├── Dockerfile                   # Multi-stage production image
├── pyproject.toml               # Project metadata, dependencies, tool config
├── uv.lock                      # Lockfile (committed)
├── Makefile                     # Common dev commands
├── .ruff.toml                   # Ruff configuration (if not in pyproject.toml)
└── .github/
    └── workflows/
        └── ci.yaml              # Lint, type-check, test pipeline
```

## Project Conventions

### Code Style
- **PEP compliance**: All code MUST comply with PEP 8 (style), PEP 257 (docstrings for public API), and PEP 484 (type annotations).
- **Formatting**: Ruff formatter (`ruff format`) is the single source of truth for code formatting. Line length: 99 characters.
- **Linting**: Ruff linter (`ruff check`) with a strict rule set. Enabled rule sets at minimum: `E`, `F`, `W`, `I`, `UP`, `S`, `B`, `A`, `C4`, `PT`, `RUF`.
- **Type annotations**: All functions and methods MUST have complete type annotations. `mypy --strict` MUST pass with zero errors.
- **Naming**: snake_case for functions, variables, and modules. PascalCase for classes. UPPER_SNAKE_CASE for constants.
- **Imports**: Sorted by Ruff (`isort` rules). Standard library first, then third-party, then local. No wildcard imports.
- **Docstrings**: Google style. Required on all public modules, classes, and functions.
- **No `Any` types**: Avoid `Any` except at true integration boundaries. Prefer explicit types and generics.

### Dependency Management
- **uv** is the sole package manager. Dependencies are declared in `pyproject.toml` under `[project.dependencies]` and `[project.optional-dependencies]`.
- `uv.lock` is committed to the repository. All CI and container builds use `uv sync --frozen` to ensure reproducible installs.
- Add dependencies: `uv add <package>`. Add dev dependencies: `uv add --group dev <package>`.
- Never use `pip install` directly.

### Architecture Patterns
- **Single async process**: One `asyncio` event loop runs the check scheduler, metrics server, and health server concurrently.
- **Separation of concerns**: Each module has a single responsibility. Checks, diagnostics, metrics, and logging are decoupled.
- **Dependency injection via function arguments**: Avoid global mutable state. Pass config, metrics collectors, and loggers explicitly.
- **Pydantic for all external data**: ConfigMap input is validated through pydantic models. No raw dict access for configuration.
- **structlog for all logging**: All log output goes through structlog configured with JSON rendering. No `print()` statements. No stdlib `logging` direct usage — structlog wraps it.

### Container Development

#### Dev Containers
The project supports development via [Dev Containers](https://containers.dev/) for a consistent, reproducible environment across IDEs.

- **Configuration**: `.devcontainer/devcontainer.json` defines the development container.
- **Base image**: Python 3.14 with uv pre-installed.
- **Included tools**: Ruff, mypy, pytest, kustomize, kubectl.
- **IDE support**:
  - **VS Code**: Open the project folder; VS Code detects `.devcontainer/` and prompts to reopen in container. Install the "Dev Containers" extension (`ms-vscode-remote.remote-containers`).
  - **JetBrains PyCharm**: Use the Dev Containers integration (PyCharm 2023.3+). Go to File → Remote Development → Dev Containers, select the project directory.
- **Post-create**: `uv sync` runs automatically after container creation to install all dependencies.
- **Volumes**: The project directory is bind-mounted. uv cache and mypy cache are stored in named volumes for persistence across rebuilds.

#### Production Dockerfile
- Multi-stage build: builder stage runs `uv sync --frozen --no-dev`, final stage copies the virtual environment into `python:3.14-slim`.
- Runs as non-root user (`egress-checker`, UID 1000).
- Exposes ports 8080 (health) and 9090 (metrics).
- Entrypoint: `python -m egress_checker`.

### IDE Configuration

#### VS Code
Recommended extensions (defined in `.vscode/extensions.json`):
- `ms-python.python` — Python language support
- `ms-python.mypy-type-checker` — mypy integration
- `charliermarsh.ruff` — Ruff linting and formatting
- `ms-vscode-remote.remote-containers` — Dev Container support

Settings (`.vscode/settings.json`):
- Default formatter: Ruff
- Format on save: enabled
- Organize imports on save: enabled (via Ruff)
- Python default interpreter: `.venv/bin/python` (from uv)
- mypy enabled in strict mode

#### JetBrains PyCharm
- Set the project interpreter to the uv-managed virtual environment (`.venv/bin/python`)
- Enable Ruff as the external formatter: Settings → Tools → External Tools
- Configure Ruff as a file watcher for format-on-save
- Enable mypy via the Mypy plugin with `--strict` flag
- Mark `src/` as Sources Root and `tests/` as Test Sources Root

### Makefile Commands
The `Makefile` provides standard development commands:

```makefile
lint        # Run ruff check
format      # Run ruff format
typecheck   # Run mypy --strict
test        # Run pytest with coverage
test-unit   # Run unit tests only
test-int    # Run integration tests only
check       # Run lint + typecheck + test (CI equivalent)
build       # Build container image
```

### Testing Strategy
This project follows **test-driven development (TDD)**. Tests are written before implementation code. No implementation is considered complete unless all relevant tests pass.

- **Framework**: pytest with pytest-asyncio for async test support.
- **Structure**: `tests/unit/` for fast isolated tests, `tests/integration/` for tests requiring a running application or network access.
- **Coverage**: pytest-cov with a minimum threshold enforced in CI. Target: 90%+ line coverage for `src/egress_checker/`.
- **TDD workflow**:
  1. Write a failing test that defines the expected behavior.
  2. Write the minimal implementation to make the test pass.
  3. Refactor while keeping tests green.
- **Naming**: Test files mirror source files (`src/egress_checker/config.py` → `tests/unit/test_config.py`). Test functions use `test_<behavior_under_test>` naming.
- **Fixtures**: Shared fixtures live in `conftest.py`. Use factory fixtures over complex setup. Prefer `tmp_path` for file-based tests.
- **Mocking**: Use `pytest-mock` or `unittest.mock`. Mock at boundaries (HTTP responses, TCP connections, file I/O). Never mock the unit under test.
- **Async tests**: Use `@pytest.mark.asyncio` decorator. Tests for check engine, scheduler, and health server are async.
- **CI gate**: All tests must pass before merge. No skipped tests without a linked issue explaining why.

### Documentation Standards

#### README.md Requirements

The project `README.md` is the primary entry point for developers, tenant teams, and platform engineers. It MUST be comprehensive and kept up to date as the project evolves. Any change that adds, modifies, or removes a user-facing feature, configuration option, metric, environment variable, CLI command, or deployment pattern MUST include a corresponding README update in the same changeset.

**Required sections** (in order):

1. **Project title and summary** — one-paragraph description of what the tool does and the ownership model (platform team vs. tenant team).
2. **Table of contents** — linked section headings for quick navigation.
3. **How It Works** — numbered step-by-step flow from tenant configuration through to observable output (metrics, logs).
4. **Architecture** — ASCII or Mermaid diagram showing the runtime component layout (pod internals, ports, data flow to Prometheus). Include a module structure tree mapping source files to responsibilities, and a bullet list of key design decisions with brief rationale.
5. **Target Configuration** — full YAML example covering every supported target type (HTTP, HTTPS, TCP, internal cluster, custom options). Include a field reference table (field, required, default, description) and a constraints subsection (max targets, min interval, uniqueness, validation behavior on invalid input).
6. **Failure Diagnostics** — table of all failure categories with trigger conditions and suggested actions. Include a heuristic disclaimer note and description of the `diagnostics` object and `suggested_action` field in logs.
7. **Prometheus Metrics** — table of all exposed metrics with name, type, labels, and description. Include example PromQL queries for common use cases (failing targets, firewall blocks, latency percentiles, alerting).
8. **Structured Logging** — example JSON for both successful and failed checks. Describe log fields, the `diagnostics` object structure, and integration with the cluster log pipeline.
9. **Local Development** — prerequisites list, quick-start commands (`uv sync`, `make check`, local run). Makefile command reference table. Dev Container setup for VS Code and JetBrains PyCharm. IDE setup without dev containers (extensions, settings, interpreter configuration).
10. **Python Development Patterns** — dependency management rules (uv only, `uv.lock` committed, `--frozen` in CI). Code style summary (PEP compliance, Ruff, mypy strict, naming, docstrings). Ruff rule set table. Logging patterns (structlog only). Configuration validation patterns (pydantic). Async patterns (bounded concurrency).
11. **Testing** — TDD methodology statement. Commands for running tests. Test directory structure with test counts per file. Testing conventions (naming, fixtures, mocking boundaries, async tests).
12. **Kubernetes Deployment** — Kustomize base manifest inventory table. Default resource profile table. Step-by-step tenant overlay guide with complete YAML examples for `kustomization.yaml` and `configmap-patch.yaml`. Build-and-deploy commands (kustomize build, hydrate, commit). Resource limit override example. Container image build and publish instructions (including multi-stage Dockerfile description). Health probe endpoint table.
13. **Environment Variables** — complete reference table of all environment variables with name, default value, and description.
14. **License** — link to LICENSE file.

**Style rules for README content:**

- Use GitHub-flavored Markdown.
- Prefer tables over long prose for reference material (fields, metrics, commands, env vars).
- Code blocks MUST specify a language (`yaml`, `bash`, `python`, `json`, `promql`).
- YAML and JSON examples MUST be valid and copy-pasteable.
- ASCII diagrams are preferred over images for architecture; they render in all terminals and editors.
- Keep each section self-contained — a reader should be able to jump to any section via the table of contents and understand it without reading prior sections.
- Do not duplicate content from `openspec/` specs or `prd.md` verbatim; the README is the user-facing reference, not the spec.

### Git Workflow
- **Branching**: Feature branches off `main`. Branch naming: `<type>/<short-description>` (e.g., `feat/add-tcp-checker`, `fix/config-validation`).
- **Commits**: Conventional Commits format — `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.
- **Pull requests**: All changes go through PR with at least one review. PR description references the relevant OpenSpec change or task.
- **CI checks on PR**: lint (`ruff check`), format verification (`ruff format --check`), type check (`mypy --strict`), tests (`pytest`). All must pass.
- **Main branch protection**: No direct pushes to `main`. Squash merge preferred.

## Domain Context
- **AKS shared cluster**: Multiple tenant teams deploy workloads on the same Azure Kubernetes Service cluster. Tenants have namespace-scoped access.
- **Azure Firewall**: Egress traffic passes through Azure Firewall managed by a separate networking team. Firewall rule changes are a common source of egress failures.
- **ArgoCD GitOps**: All Kubernetes manifests are committed as hydrated YAML to Git. ArgoCD syncs pre-rendered manifests — no server-side Kustomize or Helm processing.
- **Azure Managed Prometheus**: Metrics are scraped via PodMonitor resources. PromQL queries must be compatible with the Azure implementation.
- **Tenant isolation**: Each checker instance runs in the tenant's namespace. No cross-namespace communication. Tenants own their ConfigMap; the platform team owns the container image and Kustomize base.

## Important Constraints
- Python 3.14+ is the minimum supported version. Do not use features removed in 3.14 or rely on deprecated stdlib modules.
- Container image must stay small: target under 100MB final image size.
- Resource budget per checker instance: 32Mi–64Mi memory, 25m–50m CPU (overridable by tenants).
- Maximum 50 targets per checker instance (enforced by pydantic validation).
- Check interval minimum: 10 seconds (to prevent abuse of external endpoints).
- No persistent storage. The checker is fully stateless.
- No CRDs in Phase 1. Configuration uses standard ConfigMap.
- All Kubernetes manifests are Kustomize-based with hydrated output committed to Git.

## External Dependencies
- **Azure Managed Prometheus**: Metrics scraping target. Checker exposes `/metrics` on port 9090.
- **Azure Managed Grafana**: Dashboard visualization (Phase 2 — dashboard template).
- **ArgoCD**: GitOps deployment engine. Syncs hydrated manifests from Git.
- **CoreDNS**: Kubernetes cluster DNS. Used for resolving internal service names and as part of DNS diagnostics.
- **Azure Firewall**: Egress traffic filter. Checker heuristically detects firewall blocks but does not interact with the firewall API.
- **Container registry**: Platform team publishes versioned checker images. Registry path TBD.