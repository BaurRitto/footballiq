# FootballIQ — Codex project instructions

Read `docs/HACKATHON_CONTEXT.md` before making architectural changes. Read `README.md` for verified local commands.

## Objective
Build a working AI football intelligence application for Microsoft × Premier League **Inside the Game: Developer Hackathon**. Submission deadline: **October 27, 2026, 11:59 PM Pacific Time**. Demo video <2 minutes, public GitHub repository, project description, and a functioning application. Verify official rules independently.

## Data and intellectual property
- Hackathon requires **synthetic, football-realistic** match data. Do not pass off real Premier League events as synthetic or ship real data as the application feed.
- Kaggle historical English Premier League datasets are optional research inputs for estimating distributions; review each dataset's license before obtaining, redistributing, or training on it. Do not commit raw Kaggle downloads by default.
- Use fictional team/player names and avoid unlicensed logos, footage and music.

## Engineering conventions
- Python-first, small incremental commits, avoid unnecessary new dependencies.
- Deterministic calculations for game statistics; LLMs should explain grounded facts, not invent scores, possession, or shots.
- Tests must pass: `python -m unittest discover -s tests -v`.
- Keep seeds and synthetic provenance in generated outputs. No secrets in Git; `.env` must remain untracked.
- Avoid heavy Azure provisioning until the local match replay and MVP demonstrate value.
- Point out uncertainty and limitations; do not assert code, tests or Azure deployment have been completed unless actually verified.

## Prioritized MVP
1. Event simulator and replay (Phase 1 starter exists).
2. Calculated match metrics, event detection, and Streamlit live replay/dashboard.
3. Microsoft Foundry backed agent workflow: stats tools, tactical reasoning, commentary, personalization.
4. English/Kazakh fan versus analyst modes, grounded half-time/full-time recaps.
5. Azure deployment, documentation, tests, and <2-minute demo.

## First Codex task
Inspect repository structure, run Phase 1 tests and simulator, report findings, then propose and implement a small Phase 2 increment: deterministic rolling match statistics and detection of a sustained attacking-pressure window. Keep sample data synthetic and add tests.
