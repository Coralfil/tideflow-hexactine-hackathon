# Workspace Scripts

All automation scripts in this directory use Windows PowerShell syntax with semicolon (`;`) statement separators. Do not use double-ampersand (`&` followed by `&`) in any script or command example.

## Planned Scripts

- `dev.ps1`: Starts the FastAPI backend (`127.0.0.1:8010`) and Vite frontend (`127.0.0.1:5173`) for local development.
- `verify_all.ps1`: Runs backend `pytest`, frontend typechecking (`npm.cmd run type-check`) and build (`npm.cmd run build`), plus end-to-end and hygiene checks (zero U+2014 em dashes, semicolon `;` separators only).
- `kane_loop.ps1`: Runs closed-loop KaneCLI NDJSON verification (`kane-cli.cmd ... --agent --headless`) and Rook assurance checks (`rook.cmd ...`).

## Windows CLI Conventions

- Invoke npm and TestMu AI tools via `.cmd` shims (`npm.cmd`, `npx.cmd`, `kane-cli.cmd`, `rook.cmd`).
- Set `$env:ROOK_ENV = 'prod'` before running `rook.cmd` commands.
- Pass `--agent` to `kane-cli.cmd run`, `testmd run`, and `testrun run` so stdout emits NDJSON and never blocks on an interactive terminal view.
