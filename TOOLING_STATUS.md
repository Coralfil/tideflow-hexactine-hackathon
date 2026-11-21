# Tooling Status

Recorded from `d:\Kane Hackathon` on `2026-11-19T05:50:00Z` with `$env:ROOK_ENV = 'prod'` and `$env:NPM_CONFIG_UPDATE_NOTIFIER = 'false'`.

## Installed Packages and Versions

| Tool / Package | Installed Version | Binary Shim | Notes |
|---|---|---|---|
| `@testmuai/kane-cli` | `0.10.6` | `kane-cli.cmd` | Scoped package verified |
| `@testmuai/rook` | `0.1.21` | `rook.cmd` | Requires `$env:ROOK_ENV = 'prod'` |
| `@testmuai/kane-cli-skill` | `0.1.5` | `npx.cmd --yes @testmuai/kane-cli-skill` | Installed to `.claude`, `.agents`, `.gemini` under `%USERPROFILE%` |
| `relate` | `1.0.1` | `relate.exe` | Local database at `./data/tideflow_memory.rl` |
| `python` | `3.13.15` | `python.exe` | `fastapi`, `uvicorn`, `pydantic`, `httpx`, `neo4j`, `pytest`, `pytest_asyncio` available |
| `node` / `npm` | `v24.19.0` / `11.17.0` | `npm.cmd` | Global prefix on `$env:PATH` |

## Command Checks and Exit Codes

| Command | Exit Code | Status Summary |
|---|---|---|
| `kane-cli.cmd --version` | `0` | `0.10.6` |
| `rook.cmd --version` | `0.1.21` | `0.1.21` |
| `kane-cli.cmd whoami` | `1` | Not logged in (`Profile: default`, `Environment: prod`, `Method: none`, `Token: missing`) |
| `kane-cli.cmd config show` | `0` | `profile: default`, `env: prod`, `auth: not configured`, `model: v16-alpha`, `mode: testing`, `target: desktop` |
| `rook.cmd doctor --json` | `0` | `workspace: d:\Kane Hackathon`, `controller: reachable`, `api: reachable`, `identity: anonymous`, `auth: not signed in` |
| `rook.cmd whoami` | `1` | `not signed in` (run `rook login` interactively or supply CI credentials) |
| `relate info --database .\data\tideflow_memory.rl` | `0` | `nodes: 5`, `indexes: 6`, `constraints: 4`, `format version: 5` |

## Authentication Note

Both `kane-cli` and `rook` binaries execute cleanly from `d:\Kane Hackathon`, and both TestMu AI cloud endpoints (`rook-api.lambdatest.com`) are reachable. Interactive OAuth sign-in (`kane-cli.cmd login --oauth`, `rook.cmd login`) was skipped during automated setup to avoid blocking on a browser callback; either run those commands interactively or set `$env:LT_USERNAME` and `$env:LT_ACCESS_KEY` before running cloud-backed assurance flows.
