# Global Agent Rules

## Windows PowerShell Syntax
- **NEVER** use double-ampersand (`&` followed by `&`) as a statement separator in shell commands on Windows, as older versions of PowerShell (pre v7) do not support it and will throw a ParserError.
- **INSTEAD**, use a semicolon (`;`) to separate commands sequentially, or execute them as separate tool calls.

## Artifact Naming Convention
- When creating implementation plans or walkthrough summaries, ALWAYS date and time stamp the filename.
- Group the filename into version.subversion and sprintname using alphaphonetic naming (e.g., Alpha, Bravo).
- Example: `implementation_plan_v1.1_Alpha_2026-08-10T10-10-35.md`

## Public-Facing Materials Writing Rule
- **ALWAYS** run the `unslop` pass or apply `unslop` guidelines when writing any public-facing materials, walkthroughs, marketing copy, or company specifications.
- **ELIMINATE** AI cliches (e.g., robust, comprehensive, leverage, delve, tapestry, paradigm), excessive bulleted structures, and robotic chatbot openings/conclusions to keep all outputs direct, concise, and authentic.

## Em Dash / Punctuation Rule
- **NEVER** use em dashes (Unicode U+2014) when creating public-facing material, code, or artifacts.
- **INSTEAD**, rewrite the sentence to flow naturally, break it up into two distinct sentences, or use parentheses `(brackets)`.

## Antigravity Compute Auto-Tiering & Credit Rhythm Rule
- Whenever a user prompt produces a drafted plan (implementation plan, orchestration plan, sprint plan, or roadmap):
  1. Run `python "C:\Users\seafa\.gemini\config\scripts\credit_rhythm.py" --markdown-table` or read the rhythm context to embed the 3-Bucket Quota & Rhythm Table (`Flash 5h`, `Flash 7d`, `Argon 7d`) with KaTeX color badges (`\textcolor{#ef4444}` Red `> +15%` Fast, `\textcolor{#22c55e}` Green `-15% to +15%` On-Pace, `\textcolor{#eab308}` Yellow `< -15%` Slow).
  2. Auto-assign each task compute tier (`Flash Lite` -> `flash_lite` at `0.25x`, `Flash High` -> `flash` at `1.0x`, `Argon Med` -> `pro` at `2.5x`, base rate `1 credit / 100 effective tokens`, cached reads `0.1x`) and report per-task plus total tokens and credits, plus total credits under each override tier.
  3. Before dispatching subagents, pause and present the 5-Option Pre-Dispatch Gate via `ask_question`:
     - `(Recommended) Proceed as planned. Generate summary and update integrations and supporting documentation.`
     - `Adjust compute tiers to Flash Lite (revise plan and proceed, generate summary and update integrations and supporting documentation).`
     - `Adjust compute tiers to Flash High (revise plan and proceed, generate summary and update integrations and supporting documentation).`
     - `Adjust compute tiers to Argon Med (revise plan and proceed, generate summary and update integrations and supporting documentation).`
     - `Add specific instructions and revise plan.`
  4. If the user selects a tier adjustment (Options 2-4), run `credit_rhythm.py --set-override <tier>`, revise the plan table, execute via `invoke_subagent(Model=<tier>)`, and reset `--set-override auto` upon completion.
