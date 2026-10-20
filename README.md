# FootballIQ — synthetic match intelligence

Starter for **Inside the Game: Developer Hackathon**. Everything in this dataset is generated and fictional. No real Premier League event data or trademarks are included.

## Quick start (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m simulator.generator --seed 42 --events 800 --output data/sample_match.json
python -m unittest discover -s tests -v
python -m simulator.replay --input data/sample_match.json
```

If activation is blocked, call `.\.venv\Scripts\python.exe` instead of `python` (no policy changes required).

## Quick start (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m simulator.generator --seed 42 --events 800
python -m unittest discover -s tests -v
```

No third-party dependencies are needed for the simulator or analytics.

## Local replay dashboard

Install the dashboard dependency and start the app from this project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://127.0.0.1:8501. Use Play/Pause, replay speed, Restart, and the timeline
to inspect the match. The sidebar's example button jumps to 18:47. Statistics,
pressure evidence, onset history, and downloaded analytics reflect only events
observed at the selected time. The rolling window can be 3, 5, or 10 minutes.
The dashboard uses the checked-in fictional match and shows its seed and notice.

The UI is a thin Streamlit layer over `analytics`, with session-local replay
state and timed fragment updates. No Azure access or AI credentials are needed.
It runs on loopback by default. On macOS/Linux use `.venv/bin/python` instead.
Run tests with the virtual-environment Python to include dashboard interaction
checks; these checks skip when Streamlit is not installed. GitHub Actions installs
the dependency and runs the complete suite on pushes and pull requests.

## Phase 2: deterministic analytics

```powershell
python -m analytics --input data/sample_match.json
python -m analytics --input data/sample_match.json --at 1127 --window-seconds 300
python -m unittest discover -s tests -v
```

The JSON output includes cumulative and rolling passes, completed passes, pass
accuracy, shots, shots on target (goals plus saves), goals, tackles, interceptions,
and attacking-event counts. The score comes from observed goal events, never the
stored final score. `--at` sets a replay cutoff in match seconds and omits future
events and full-match pressure history. Without `--at`, analysis ends at match
duration and includes pressure onsets throughout the match.

Python API: `analytics.analyze_match(match, as_of_seconds=1127,
window_seconds=300)` and `analytics.detect_pressure(match)`. Both preserve the
match ID, seed, synthetic flag, and data notice, validate the synthetic feed, and
leave inputs unchanged. Invalid feeds/options raise `ValueError`.

Rolling windows include events in `(cutoff - window_seconds, cutoff]`; an event
exactly at the left boundary expires. Events at time zero count in early windows.
Equal timestamps are evaluated together. Empty windows return zero statistics.
The existing generator `summarize` API remains available for compatibility.

Pressure is an explainable heuristic, with configurable `PressureConfig` defaults:

- At least two shots and five attacking events within five minutes.
- Attacking events are shots or completed passes with `x >= 66.666...`.
- Evidence spans at least 60 seconds.
- The team has at least 65% of both teams' attacking events in that window.

Coordinates are interpreted relative to each team's attacking goal. Activity
share is **not possession**. The source has no reliable possession timeline, so
no possession percentage is reported. This heuristic is not calibrated against
real matches and does not measure tracking-based pressure or xG. Evidence span
is a minimum-duration proxy, not proof of uninterrupted control.

Each pressure signal includes its window, event IDs, shot count, activity share,
and evidence span. The batch detector emits one onset per active episode and
allows reactivation after pressure drops. It evaluates event times and window
expirations, including quiet gaps. Calculations use simple in-memory scans for
the small synthetic MVP feed; incremental streaming aggregation is deferred.

Verified example (`--seed 42 --events 800`): Blue FC triggers pressure at **18:47**
in the window `(13:47, 18:47]`. Evidence comprises completed advanced passes
`evt-0140`, `evt-0153`, `evt-0155`, `evt-0168`, and blocked shots `evt-0151`,
`evt-0160`. These six events span 189 seconds and account for 6 of 9 attacking
events (66.67%) in that window. This is synthetic evidence, not a real match.

## Data contract

Each event has: `event_id`, `match_id`, `minute`, `second`, `team`, `player_id`, `event_type`, `outcome`, `location` (normalized x/y from 0 to 100), `synthetic`.

Events are ordered by match clock. Summary statistics can be calculated with `summarize(match)` in `simulator/generator.py`.

**Limitations:** This is a *simplified synthetic event stream*, not a physics-accurate match simulation. Passing locations and possession transitions are approximate. The event count is configurable, but event frequency does not reproduce professional tracking data; possession must not be calculated from counts of events. Add a proper possession timeline in Phase 2.

## Phase 1 checklist

- [ ] Register on the hackathon website and check the official rules
- [ ] Create a new public GitHub repository `footballiq` (avoid uploading credentials)
- [x] Initialize Python project
- [x] Define event contract
- [x] Build seeded synthetic event generator
- [x] Generate one full 90-minute match
- [x] Add basic automated tests
- [ ] Provision Microsoft Foundry project, assign appropriate permissions, deploy a supported model

## Foundry configuration (for later phases)

Follow [official Foundry SDK setup](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/sdk-overview).

- Create a Foundry project in an Azure subscription you control.
- Deploy a model available in your region and quota, set budget/spending alerts in Azure.
- Use Entra ID / Azure CLI login (`az login`) instead of saving keys in your repo.
- Store the Foundry project endpoint and model deployment name in local environment variables; do not commit secrets.
- Phase 3 can use `pip install agent-framework-foundry`, per the [Agent Framework project](https://github.com/microsoft/agent-framework). Integrate only once core data flow is stable.

## Next phase

Rolling statistics, attacking-pressure detection, and feed validation are
implemented, together with a local replay dashboard. Next: a coherent possession
timeline in the simulator, and later evidence-grounded AI explanations.

## Working with Codex in VS Code

For the full project handoff from ChatGPT, read `docs/HACKATHON_CONTEXT.md`.
Codex project rules are in `AGENTS.md`; tell Codex to read both and inspect the implementation before continuing.
