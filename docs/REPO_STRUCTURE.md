# Repo Structure

This repository is organized around four product layers:

1. Go MCP server
2. Browser/runtime primitives
3. Python orchestration
4. Runnable examples and validation

## Top-Level Layout

| Path | Purpose |
|---|---|
| `README.md` | Main project overview, setup, smoke-test entry points |
| `CONTRIBUTING.md` | Contribution and authoring guide |
| `Makefile` | Common build, install, and smoke-test commands |
| `cmd/server/` | Go entrypoint and MCP tool registration |
| `pkg/` | Go implementation packages |
| `orchestrator/` | Python recipe generator and workflow runner |
| `examples/` | Demos, E2E flows, smoke checks, and reference clients |
| `extensions/` | Dynamic plugin definitions |
| `docs/` | Repository structure and supplementary project documentation |

## Go Runtime Layout

| Path | Responsibility |
|---|---|
| `cmd/server/main.go` | Process startup, transport selection, browser/agent initialization |
| `cmd/server/tools.go` | MCP tool registration and request handlers |
| `pkg/browser/` | Playwright engine, tabs, screenshots, page context, humanized actions |
| `pkg/agent/` | Prompt reframing, element finding, extraction, memory, parallel work |
| `pkg/stealth/` | Embedded stealth/fingerprint patches |
| `pkg/plugins/` | Dynamic MCP plugin loading |
| `pkg/transport/` | Alternate transports such as SSE |

## Orchestrator Layout

| Path | Responsibility |
|---|---|
| `orchestrator/orchestrator.py` | Natural-language recipe generation and execution |
| `orchestrator/recipes/` | Reusable multi-step workflows |
| `orchestrator/selectors/` | Site-specific selector catalog |
| `orchestrator/ui.py` | Terminal UX helpers for orchestrator runs |

## Examples Layout

Examples are currently kept in one folder for easy discoverability, but they follow naming conventions:

| Prefix / file | Purpose |
|---|---|
| `e2e_*.py` | End-to-end product demos against live websites |
| `test_*.py` | Validation and integration checks |
| `smoke_major_sites.py` | Prompt-driven smoke suite for major public websites |
| `client.py` | Shared stdio MCP client used by example scripts |
| `*_voice_*.py`, `ui_voice_agent.py`, `wavy_voice_app.py` | Experimental voice-driven demos |

## Conventions For New Files

- Add new MCP server code under `pkg/` or `cmd/server/`, not at the repo root.
- Add new recipes under `orchestrator/recipes/`.
- Add new selectors under `orchestrator/selectors/`.
- Add runnable demos under `examples/` and keep the filename prefix meaningful.
- Add long-form documentation under `docs/` unless it is core onboarding content for `README.md`.

## Generated Artifacts

These are considered local/generated artifacts and should stay out of version control:

- Python bytecode and `.pycache/`
- smoke logs in `.smoke-logs/`
- temporary logs, `.orig`, and `.patch` files
- local audio scratch files such as `temp_command.wav`

## Suggested Mental Model

If you are changing:

- browser mechanics: start in `pkg/browser/`
- LLM navigation or extraction: start in `pkg/agent/`
- natural-language workflows: start in `orchestrator/orchestrator.py`
- site-specific reliability: start in `orchestrator/selectors/`
- demos and validation: start in `examples/`
