"""Local synthetic match replay. All football facts come from analytics."""

import json
from pathlib import Path
import time

import streamlit as st

from analytics import analyze_match, detect_pressure, validate_match

st.set_page_config(page_title="FootballIQ | Match intelligence", page_icon="⚽", layout="wide")


@st.cache_data
def load_match():
    match = json.loads((Path(__file__).parent / "data" / "sample_match.json").read_text(encoding="utf-8"))
    validate_match(match)
    return match


@st.cache_data
def pressure_history(match, window):
    return detect_pressure(match, window_seconds=window)["signals"]


def clock(seconds):
    minute, second = divmod(int(seconds), 60)
    return f"{minute:02d}:{second:02d}"


def seek():
    st.session_state.last_clock = time.monotonic()


def toggle():
    st.session_state.playing = not st.session_state.playing
    seek()


def jump(seconds):
    st.session_state.position = seconds
    st.session_state.playing = False
    seek()


def event_rows(events):
    return [{
        "Clock": clock(e["minute"] * 60 + e["second"]),
        "Team": e["team"], "Player": e.get("player_id", "Unknown"),
        "Event": e["event_type"], "Outcome": e["outcome"],
        "x": e["location"]["x"], "y": e["location"]["y"], "Event ID": e["event_id"],
    } for e in events]


try:
    match = load_match()
except (OSError, ValueError) as error:
    st.error(f"Cannot load the synthetic match: {error}")
    st.stop()

duration = int(match["duration_minutes"] * 60)
for key, value in {"position": 0, "playing": False, "last_clock": time.monotonic()}.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("FootballIQ")
st.caption("MATCH INTELLIGENCE · SYNTHETIC REPLAY")
st.info(match["data_notice"])
with st.sidebar:
    st.header("Replay settings")
    speed = st.select_slider("Replay speed", options=[1, 5, 15, 30, 60], value=30, on_change=seek)
    window = st.selectbox("Rolling window (minutes)", [3, 5, 10], index=1) * 60
    st.caption(f"Match {match['match_id']} · Seed {match['seed']} · {len(match['events'])} fictional events")
    st.caption("Pressure is a heuristic based on shots and advanced completed passes. Activity share is not possession.")
    with st.expander("Pressure rule"):
        st.write("At least 2 shots, 5 attacking events, a 60-second evidence span, and 65% of attacking activity in the selected window.")
    st.button("Jump to example · 18:47", on_click=jump, args=(1127,))


@st.fragment(run_every=0.5)
def replay():
    now = time.monotonic()
    if st.session_state.playing:
        elapsed = int((now - st.session_state.last_clock) * speed)
        if elapsed:
            st.session_state.position = min(duration, st.session_state.position + elapsed)
            st.session_state.last_clock += elapsed / speed
        if st.session_state.position == duration:
            st.session_state.playing = False

    controls = st.columns([1, 1, 4])
    controls[0].button("Pause" if st.session_state.playing else "Play", on_click=toggle,
                       disabled=st.session_state.position == duration)
    controls[1].button("Restart", on_click=jump, args=(0,))
    controls[2].caption(f"{speed}× speed · {'Playing' if st.session_state.playing else 'Paused'}")
    cutoff = st.slider("Match timeline (seconds)", 0, duration, key="position", on_change=seek)
    snapshot = analyze_match(match, as_of_seconds=cutoff, window_seconds=window)
    home, away = match["teams"]
    board = st.columns([2, 1, 2])
    board[0].metric(home, snapshot["score"][home])
    board[1].metric("Match clock", clock(cutoff))
    board[2].metric(away, snapshot["score"][away])
    st.progress(cutoff / duration)

    stats_tab, evidence_tab = st.tabs(["Match statistics", "Event evidence"])
    with stats_tab:
        totals, rolling = st.columns(2)
        for panel, key, title in ((totals, "cumulative", "Match so far"),
                                  (rolling, "rolling", f"Last {window // 60} minutes")):
            panel.subheader(title)
            rows = [{"Metric": metric.replace("_", " ").title(),
                     home: snapshot[key][home][metric], away: snapshot[key][away][metric]}
                    for metric in ("shots", "shots_on_target", "passes", "completed_passes",
                                   "pass_accuracy_pct", "tackles", "interceptions", "attacking_events")]
            panel.dataframe(rows, hide_index=True, width="stretch")

    st.subheader("Attacking pressure")
    if not snapshot["pressure"]:
        st.caption("No team meets the sustained-pressure rule at this moment.")
    for signal in snapshot["pressure"]:
        st.success(f"{signal['team']} · {signal['shots']} shots · "
                   f"{signal['attacking_events']} attacking events · "
                   f"{signal['attacking_activity_share']:.1%} of attacking activity")
        st.caption(f"Evidence spans {signal['span_seconds']} seconds in the last {window // 60} minutes.")
        with st.expander(f"Inspect evidence · {signal['team']}"):
            ids = set(signal["evidence_event_ids"])
            st.dataframe(event_rows([e for e in match["events"] if e["event_id"] in ids]),
                         hide_index=True, width="stretch")

    history = [s for s in pressure_history(match, window) if s["detected_at_seconds"] <= cutoff]
    with st.expander(f"Pressure onset history · {len(history)} episodes"):
        st.dataframe([{"Clock": clock(s["detected_at_seconds"]), "Team": s["team"],
                       "Shots": s["shots"], "Attacking events": s["attacking_events"]}
                      for s in history], hide_index=True, width="stretch")
    with evidence_tab:
        observed = [e for e in match["events"] if e["minute"] * 60 + e["second"] <= cutoff]
        st.caption(f"{len(observed)} observed events · newest first")
        st.dataframe(event_rows(list(reversed(observed))), hide_index=True, width="stretch")
    st.download_button("Download current analytics", json.dumps(snapshot, indent=2),
                       file_name=f"synthetic_analytics_{cutoff}.json", mime="application/json")


replay()
