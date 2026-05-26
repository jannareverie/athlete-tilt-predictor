"""
Athlete Cognitive Stability Analyzer — v4
Adds team-aggregate analysis: 12 player feeds per team, each scored individually,
rolled up into a roster-level stability index. Same cached-fallback architecture
as v3 — every number on screen is a real model output (live or cached).

To populate the team cache:
  1. Set OPENAI_API_KEY.
  2. Select "Wildcats vs Spartans (Team Aggregate)" → Run analysis.
  3. The per-player results are computed live and aggregated automatically.
  4. Open the "Raw JSON" expander and copy the player_results block into
     TEAM_ANALYSIS_CACHE below for future zero-API runs.
"""

import json
import os
import random
import statistics
import streamlit as st
import plotly.graph_objects as go

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ---------- Page config ----------
st.set_page_config(
    page_title="Athlete Cognitive Stability Analyzer",
    page_icon="🧠",
    layout="wide",
)

# ---------- Constants ----------
DIMENSIONS = [
    "emotional_regulation",
    "cognitive_load",
    "risk_assessment",
    "stress_indicators",
]

DIMENSION_LABELS = {
    "emotional_regulation": "Emotional Regulation",
    "cognitive_load": "Cognitive Load",
    "risk_assessment": "Risk Assessment",
    "stress_indicators": "Stress Indicators",
}

ANALYSIS_PROMPT = """You are a sports psychology analyst evaluating athlete communication for cognitive stability. Analyze the following text across four dimensions. For each dimension, provide a score from 0 to 100 (where 100 = optimal stability) and a brief justification.

Dimensions:
1. emotional_regulation: composure, measured language, ability to discuss setbacks without volatility.
2. cognitive_load: mental clarity, coherent reasoning, organized thought.
3. risk_assessment: balanced perspective, realistic appraisal of consequences.
4. stress_indicators: absence of acute stress markers — relaxed phrasing, confidence.

Return ONLY valid JSON in this exact schema:
{
  "emotional_regulation": {"score": <int 0-100>, "justification": "<one sentence>"},
  "cognitive_load": {"score": <int 0-100>, "justification": "<one sentence>"},
  "risk_assessment": {"score": <int 0-100>, "justification": "<one sentence>"},
  "stress_indicators": {"score": <int 0-100>, "justification": "<one sentence>"},
  "overall_stability_index": <int 0-100>,
  "summary": "<2-3 sentence overall read>",
  "key_signals": ["<short phrase>", "<short phrase>", "<short phrase>"]
}

TEXT TO ANALYZE:
---
{text}
---
"""

# ---------- Individual athlete feeds ----------
DEMO_FEEDS = {
    "Marcus Vale (NBA — SG)": {
        "type": "individual",
        "prop_market": "Marcus Vale to score 25+ points tonight",
        "items": [
            {"source": "Post-game presser, 18hr ago", "text": "Look, I don't really care what the analysts say. I've been hearing it my whole career. The system isn't built for guys like me. Tonight wasn't on me — half the team didn't show up. I'm done answering questions about my shot selection. Next question. Actually, no, we're done here."},
            {"source": "Instagram story, 9hr ago", "text": "Some people in this building forgot who I am. That's fine. Y'all gonna remember."},
            {"source": "Shootaround availability, 2hr ago", "text": "Yeah I'm good. I'm always good. Doesn't matter what anyone writes. I'll let the game speak."},
        ],
    },
    "Eli Marston (NFL — QB)": {
        "type": "individual",
        "prop_market": "Eli Marston 250+ passing yards Sunday",
        "items": [
            {"source": "Weekly presser, 30hr ago", "text": "We had a tough loss last week, no question. But the tape showed me things I can build on. The offensive line is communicating better, the receivers are running cleaner routes, and honestly I felt calm out there even when the pocket broke down. We're focused on Sunday. One play at a time."},
            {"source": "Team podcast, 12hr ago", "text": "I've been in this league long enough to know the noise doesn't matter. What matters is preparation. The guys around me have been incredible this week."},
            {"source": "Practice availability, 1hr ago", "text": "Feeling good. Body's fresh. Game plan's tight. Looking forward to Sunday."},
        ],
    },
    "Sana Okafor (Tennis — WTA)": {
        "type": "individual",
        "prop_market": "Sana Okafor to win her R16 match in straight sets",
        "items": [
            {"source": "Post-match interview, 22hr ago", "text": "Honestly I don't know what's happening with my serve right now. It just — it's not landing. And then I get tight, and then I start thinking, and then it gets worse. I'm trying to stay positive but it's hard. It's really hard."},
            {"source": "Press conference, 14hr ago", "text": "I keep replaying that third set in my head. The double faults. I shouldn't have done that. My coach says forget it but I can't really forget it. Tomorrow's another match, I guess. We'll see."},
            {"source": "Twitter, 4hr ago", "text": "thank you to everyone sending love. trying to focus. it's a process."},
        ],
    },
    "Dimitri Kovacs (Soccer — Forward)": {
        "type": "individual",
        "prop_market": "Dimitri Kovacs to score or assist in next match",
        "items": [
            {"source": "Mixed zone, 26hr ago", "text": "The boss has been clear with me about my role. I trust him completely. When the chances come I will take them. My job is to be ready, to keep working, and to support the team whether I start or come from the bench."},
            {"source": "Training ground interview, 8hr ago", "text": "I feel sharp. The legs are good. The finishing in training has been clean. I am calm. The team is in a good place and that helps everyone."},
            {"source": "Instagram, 3hr ago", "text": "Final session done. Locked in. 💪"},
        ],
    },
}

# ---------- Team roster feeds ----------
# Wildcats: deliberately written to express defensiveness, blame attribution,
# rumination, frustration with coaching/teammates. Designed to produce lower
# stability scores from the model.
# Spartans: deliberately written to express composure, process focus, accountability,
# team-orientation. Designed to produce higher stability scores.
# Actual numbers will come from the real model run.
WILDCATS_ROSTER = [
    {
        "player": "J. Rourke (PG, Senior)",
        "items": [
            {"source": "Post-practice availability, 30hr ago", "text": "I don't know what they want from me. Every time down the floor it's a different play call. I just play."},
            {"source": "Instagram, 10hr ago", "text": "real ones know."},
        ],
    },
    {
        "player": "D. Marquez (SG, Junior)",
        "items": [
            {"source": "Local radio spot, 28hr ago", "text": "Honestly, our offense is broken. I said what I said. I'll take the heat for it but somebody had to say it."},
            {"source": "Twitter, 6hr ago", "text": "if I get my touches we win. simple as that."},
        ],
    },
    {
        "player": "T. Bishop (SF, Senior)",
        "items": [
            {"source": "Locker room scrum, 20hr ago", "text": "The refs been calling it the same way all season against us. Same crew tonight. We'll see."},
            {"source": "Postgame X reply, 4hr ago", "text": "y'all watched a different game than me."},
        ],
    },
    {
        "player": "K. Ndiaye (PF, Sophomore)",
        "items": [
            {"source": "Pre-practice media, 26hr ago", "text": "I keep thinking about that last possession. I should have boxed out. Coach told me to move on but I keep seeing it."},
            {"source": "Group text screenshot reposted on TikTok, 8hr ago", "text": "honestly I'm not even sure I should be starting rn."},
        ],
    },
    {
        "player": "R. Halverson (C, Junior)",
        "items": [
            {"source": "Shootaround, 22hr ago", "text": "Whatever. I do my job. Other guys gotta do theirs. That's all I'll say."},
            {"source": "Snapchat story, 5hr ago", "text": "frustrating week. trying to keep my head."},
        ],
    },
    {
        "player": "C. Wexler (PG, Freshman)",
        "items": [
            {"source": "School newspaper interview, 32hr ago", "text": "It's hard. The speed is hard. Everyone says it gets easier but right now it's just hard. I'm trying."},
            {"source": "Coach's podcast guest spot, 12hr ago", "text": "I made some bad reads. I know I made bad reads. I'm just trying not to make them again, but then I'm thinking about it too much, you know?"},
        ],
    },
    {
        "player": "A. Petrov (SG, Sophomore)",
        "items": [
            {"source": "Locker stall, 18hr ago", "text": "We're a better team than this. I don't care what the standings say. People in this room know."},
            {"source": "Instagram, 7hr ago", "text": "✋📈 watch."},
        ],
    },
    {
        "player": "L. Asante (SF, Junior)",
        "items": [
            {"source": "Hallway interview, 24hr ago", "text": "Game plan was the game plan. I followed it. If you got questions about the plan you should ask coach."},
            {"source": "Twitter reply, 3hr ago", "text": "wasn't on me bruh."},
        ],
    },
    {
        "player": "M. Donnelly (PF, Senior)",
        "items": [
            {"source": "Captain's presser, 30hr ago", "text": "Look, I've been here four years. I've seen this group quit on things before. I'm not saying we're there. But I'm watching."},
            {"source": "Player-run podcast, 11hr ago", "text": "some guys want it more than others. I'll leave it at that."},
        ],
    },
    {
        "player": "S. Yamada (C, Sophomore)",
        "items": [
            {"source": "Practice exit, 16hr ago", "text": "My minutes have been weird. I don't really know what they're going for with the rotation. I just stay ready."},
            {"source": "Instagram comment, 5hr ago", "text": "🤷‍♂️"},
        ],
    },
    {
        "player": "B. Connolly (PG, Junior)",
        "items": [
            {"source": "Booster club Q&A clip, 28hr ago", "text": "The expectations on this program are unfair. Everyone wants us to be a top-25 team and they don't see the roster we actually have."},
            {"source": "X post, 9hr ago", "text": "press just makes things up at this point."},
        ],
    },
    {
        "player": "F. Okolie (SF, Freshman)",
        "items": [
            {"source": "Team-produced video, 33hr ago", "text": "I came here to play and I'm barely playing. My family didn't sign up for me to sit. I'm not gonna sit."},
            {"source": "Group chat leak quoted in Athletic article, 6hr ago", "text": "honestly considering my options at the end of the year."},
        ],
    },
]

SPARTANS_ROSTER = [
    {
        "player": "H. Castellanos (PG, Senior)",
        "items": [
            {"source": "Weekly presser, 30hr ago", "text": "Coach has us focused on the next 40 minutes. That's it. We've done the work, the prep has been clean, and the guys are in a good headspace."},
            {"source": "Captain's podcast, 8hr ago", "text": "I'm proud of how this group has handled the noise. We're just getting better in small ways every day."},
        ],
    },
    {
        "player": "W. Tanaka (SG, Junior)",
        "items": [
            {"source": "Practice availability, 26hr ago", "text": "Last game I left points on the floor. I've been in the gym since. That's the job. You miss, you come back, you make the next one."},
            {"source": "Instagram, 5hr ago", "text": "good week of work. ready."},
        ],
    },
    {
        "player": "I. Berhane (SF, Senior)",
        "items": [
            {"source": "Locker room media, 22hr ago", "text": "We respect the matchup. They've got good players. Our job is just to play our game and execute the plan."},
            {"source": "School podcast, 7hr ago", "text": "I trust everyone in that room. That's the difference this year."},
        ],
    },
    {
        "player": "N. Petersen (PF, Junior)",
        "items": [
            {"source": "Post-shootaround, 19hr ago", "text": "Felt good today. The scout was clear. Everyone knows their role. Just gotta go execute."},
            {"source": "Twitter, 4hr ago", "text": "love this team. let's work."},
        ],
    },
    {
        "player": "D. Olawale (C, Senior)",
        "items": [
            {"source": "Press conference, 27hr ago", "text": "It's my last year and I'm not gonna waste a minute of it. I'm grateful. I'm prepared. I'm calm."},
            {"source": "Instagram caption, 10hr ago", "text": "one more chance to play with my brothers. that's everything."},
        ],
    },
    {
        "player": "G. Salinger (PG, Sophomore)",
        "items": [
            {"source": "Hallway scrum, 24hr ago", "text": "I learn something every game from H. He's been showing me how to manage the tempo. Just trying to soak it up."},
            {"source": "Team Q&A, 6hr ago", "text": "I think we're playing our best ball right now. Quiet confidence in the room."},
        ],
    },
    {
        "player": "Q. Bauer (SG, Freshman)",
        "items": [
            {"source": "Freshman feature piece, 32hr ago", "text": "The seniors set the tone here. I'm just trying to follow it. Show up, work, repeat."},
            {"source": "Practice exit, 12hr ago", "text": "Coach gave me good notes today. Going to study film tonight and come back better."},
        ],
    },
    {
        "player": "R. Albright (SF, Junior)",
        "items": [
            {"source": "Booster event, 28hr ago", "text": "We don't get caught up in the rankings. We focus on the next possession. That's the only thing we can control."},
            {"source": "Instagram story, 9hr ago", "text": "process > everything."},
        ],
    },
    {
        "player": "T. Voss (PF, Senior)",
        "items": [
            {"source": "Captain's presser, 31hr ago", "text": "We've lost before. We've won before. The thing that's stayed the same is how this group prepares. That's why I'm confident."},
            {"source": "Locker stall, 13hr ago", "text": "I love these guys. I love going to work with them."},
        ],
    },
    {
        "player": "P. Solis (C, Sophomore)",
        "items": [
            {"source": "Practice scrum, 20hr ago", "text": "I had a rough stretch a month ago. The staff stuck with me. I worked through it. I feel like a different player now."},
            {"source": "Team podcast, 7hr ago", "text": "It's a long season. You learn to keep an even keel."},
        ],
    },
    {
        "player": "M. Ferreira (PG, Junior)",
        "items": [
            {"source": "Pregame interview, 25hr ago", "text": "We respect everyone we play. Doesn't matter the record. We come in with the same approach every night."},
            {"source": "X post, 5hr ago", "text": "ready to compete. that's all you can ask for."},
        ],
    },
    {
        "player": "K. Larsen (SF, Freshman)",
        "items": [
            {"source": "Player development feature, 33hr ago", "text": "I'm earning my minutes one rep at a time. The vets have been great about teaching me. I feel ready when my number's called."},
            {"source": "Instagram, 8hr ago", "text": "grateful. locked in."},
        ],
    },
]

DEMO_FEEDS["Wildcats vs Spartans (Team Aggregate)"] = {
    "type": "team",
    "prop_market": "Wildcats moneyline vs Spartans",
    "wildcats": WILDCATS_ROSTER,
    "spartans": SPARTANS_ROSTER,
}

# ---------- Individual analysis cache (v3 carryover) ----------
ANALYSIS_CACHE = {
    "Marcus Vale (NBA — SG)": {
        "emotional_regulation": {"score": 30, "justification": "PLACEHOLDER — replace with real model output."},
        "cognitive_load": {"score": 45, "justification": "PLACEHOLDER — replace with real model output."},
        "risk_assessment": {"score": 35, "justification": "PLACEHOLDER — replace with real model output."},
        "stress_indicators": {"score": 30, "justification": "PLACEHOLDER — replace with real model output."},
        "overall_stability_index": 35,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": ["PLACEHOLDER 1", "PLACEHOLDER 2", "PLACEHOLDER 3"],
    },
    "Eli Marston (NFL — QB)": {
        "emotional_regulation": {"score": 82, "justification": "PLACEHOLDER — replace with real model output."},
        "cognitive_load": {"score": 85, "justification": "PLACEHOLDER — replace with real model output."},
        "risk_assessment": {"score": 78, "justification": "PLACEHOLDER — replace with real model output."},
        "stress_indicators": {"score": 80, "justification": "PLACEHOLDER — replace with real model output."},
        "overall_stability_index": 81,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": ["PLACEHOLDER 1", "PLACEHOLDER 2", "PLACEHOLDER 3"],
    },
    "Sana Okafor (Tennis — WTA)": {
        "emotional_regulation": {"score": 40, "justification": "PLACEHOLDER — replace with real model output."},
        "cognitive_load": {"score": 38, "justification": "PLACEHOLDER — replace with real model output."},
        "risk_assessment": {"score": 50, "justification": "PLACEHOLDER — replace with real model output."},
        "stress_indicators": {"score": 35, "justification": "PLACEHOLDER — replace with real model output."},
        "overall_stability_index": 41,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": ["PLACEHOLDER 1", "PLACEHOLDER 2", "PLACEHOLDER 3"],
    },
    "Dimitri Kovacs (Soccer — Forward)": {
        "emotional_regulation": {"score": 84, "justification": "PLACEHOLDER — replace with real model output."},
        "cognitive_load": {"score": 80, "justification": "PLACEHOLDER — replace with real model output."},
        "risk_assessment": {"score": 82, "justification": "PLACEHOLDER — replace with real model output."},
        "stress_indicators": {"score": 85, "justification": "PLACEHOLDER — replace with real model output."},
        "overall_stability_index": 83,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": ["PLACEHOLDER 1", "PLACEHOLDER 2", "PLACEHOLDER 3"],
    },
}

# ---------- Team analysis cache ----------
# Populate this by running live with an API key, then copy the player_results
# block from the Raw JSON expander. Until then the team selector will require
# a live key.
TEAM_ANALYSIS_CACHE = {
    "Wildcats vs Spartans (Team Aggregate)": None,  # set after first live run
}


# ---------- Live analysis ----------
def analyze_live(text: str, api_key: str, model: str = "gpt-4o") -> dict:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise sports psychology analyst. Return only valid JSON."},
            {"role": "user", "content": ANALYSIS_PROMPT.replace("{text}", text)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ---------- Aggregation ----------
def aggregate_player_results(player_results: list) -> dict:
    """
    Roll up per-player JSON results into a team-level stability profile.
    Mean across players for each dimension; mean of overall_stability_index
    for the headline number.
    """
    n = len(player_results)
    if n == 0:
        return {}

    def dim_mean(dim: str) -> int:
        return round(statistics.mean(r[dim]["score"] for r in player_results))

    def overall_mean() -> int:
        return round(statistics.mean(r["overall_stability_index"] for r in player_results))

    # Build aggregate justifications: mention spread (min/max) per dimension
    def dim_summary(dim: str) -> str:
        scores = [r[dim]["score"] for r in player_results]
        return (
            f"Roster mean {dim_mean(dim)}/100 across {n} players "
            f"(range {min(scores)}–{max(scores)})."
        )

    return {
        d: {"score": dim_mean(d), "justification": dim_summary(d)} for d in DIMENSIONS
    } | {
        "overall_stability_index": overall_mean(),
        "summary": (
            f"Aggregate across {n} players. Mean stability index: {overall_mean()}/100. "
            f"See per-player breakdown for individual contributors."
        ),
        "key_signals": [
            f"{n} players analyzed",
            f"Lowest individual: {min(r['overall_stability_index'] for r in player_results)}",
            f"Highest individual: {max(r['overall_stability_index'] for r in player_results)}",
        ],
    }


def analyze_team(api_key: str, model: str, wildcats: list, spartans: list):
    """
    Run analysis for every player on both rosters, then aggregate per team.
    Returns a dict with both team aggregates and the raw per-player results.
    """
    def run_roster(roster: list) -> list:
        results = []
        for player in roster:
            combined = "\n\n".join(
                f"[{item['source']}]\n{item['text']}" for item in player["items"]
            )
            result = analyze_live(combined, api_key, model)
            result["_player"] = player["player"]
            results.append(result)
        return results

    wildcats_results = run_roster(wildcats)
    spartans_results = run_roster(spartans)

    return {
        "wildcats": {
            "aggregate": aggregate_player_results(wildcats_results),
            "player_results": wildcats_results,
        },
        "spartans": {
            "aggregate": aggregate_player_results(spartans_results),
            "player_results": spartans_results,
        },
    }


def analyze(athlete_key: str, feed: dict, api_key: str, model: str):
    """Returns (result_dict, source_label). Result shape depends on feed type."""
    is_team = feed.get("type") == "team"

    if is_team:
        if api_key and OPENAI_AVAILABLE:
            try:
                progress = st.progress(0, text="Analyzing roster (0/24)...")
                # Inline roster runner so we can show progress
                def run_with_progress(roster, start_idx, total):
                    results = []
                    for i, player in enumerate(roster):
                        combined = "\n\n".join(
                            f"[{item['source']}]\n{item['text']}" for item in player["items"]
                        )
                        r = analyze_live(combined, api_key, model)
                        r["_player"] = player["player"]
                        results.append(r)
                        done = start_idx + i + 1
                        progress.progress(done / total, text=f"Analyzing roster ({done}/{total})...")
                    return results

                total = len(feed["wildcats"]) + len(feed["spartans"])
                wildcats_results = run_with_progress(feed["wildcats"], 0, total)
                spartans_results = run_with_progress(feed["spartans"], len(feed["wildcats"]), total)
                progress.empty()

                team_result = {
                    "wildcats": {
                        "aggregate": aggregate_player_results(wildcats_results),
                        "player_results": wildcats_results,
                    },
                    "spartans": {
                        "aggregate": aggregate_player_results(spartans_results),
                        "player_results": spartans_results,
                    },
                }
                return team_result, "live"
            except Exception as e:
                st.warning(f"Live team analysis failed ({e}); falling back to cache.")
                cached = TEAM_ANALYSIS_CACHE.get(athlete_key)
                if cached is None:
                    st.error("No cached team result available. Need a working API key for first run.")
                    return None, "unavailable"
                return cached, "cached (live attempt failed)"
        else:
            cached = TEAM_ANALYSIS_CACHE.get(athlete_key)
            if cached is None:
                st.error(
                    "Team aggregate has not been cached yet. Add an API key to run the first analysis, "
                    "then copy the result into TEAM_ANALYSIS_CACHE."
                )
                return None, "unavailable"
            return cached, "cached"

    # Individual athlete
    if api_key and OPENAI_AVAILABLE:
        combined = "\n\n".join(
            f"[{item['source']}]\n{item['text']}" for item in feed["items"]
        )
        try:
            return analyze_live(combined, api_key, model), "live"
        except Exception as e:
            st.warning(f"Live analysis failed ({e}); falling back to cached result.")
            return ANALYSIS_CACHE[athlete_key], "cached (live attempt failed)"
    return ANALYSIS_CACHE[athlete_key], "cached"


# ---------- Mock Polymarket ----------
def mock_polymarket_odds(athlete_key: str) -> dict:
    seed = sum(ord(c) for c in athlete_key)
    rng = random.Random(seed)
    base = rng.uniform(0.35, 0.85)
    jitter = (random.random() - 0.5) * 0.02
    prob = max(0.01, min(0.99, base + jitter))
    return {
        "implied_probability": round(prob * 100, 1),
        "yes_price": round(prob, 3),
        "no_price": round(1 - prob, 3),
        "volume_24h_usd": rng.randint(8_000, 240_000),
        "source": "MOCK (swap for py-clob-client in production)",
    }


# ---------- Divergence signal ----------
def divergence_signal(market_prob: float, stability_score: int) -> dict:
    delta = market_prob - stability_score
    abs_delta = abs(delta)

    if abs_delta < 15:
        level, color = "ALIGNED", "#6b7280"
        action = "No divergence — market and psych signal agree."
    elif abs_delta < 30:
        level, color = "WATCH", "#eab308"
        action = "Moderate divergence. Worth monitoring; not actionable on this signal alone."
    else:
        level = "STRONG DIVERGENCE"
        if delta > 0:
            color = "#ef4444"
            action = (
                "Market is significantly more optimistic than the psychological signal. "
                "Research hypothesis: market may be underweighting recent communication signals. "
                "NOT a trading recommendation — backtest before acting."
            )
        else:
            color = "#22c55e"
            action = (
                "Psychological signal is significantly more optimistic than the market. "
                "Research hypothesis: market may be overweighting recent negative news. "
                "NOT a trading recommendation — backtest before acting."
            )

    return {"level": level, "delta": round(delta, 1), "abs_delta": round(abs_delta, 1), "color": color, "action": action}


# ---------- Visualizations ----------
def score_color(s: float) -> str:
    if s >= 75: return "#22c55e"
    if s >= 50: return "#eab308"
    if s >= 25: return "#f97316"
    return "#ef4444"


def gauge_chart(score: float, title: str, color_override: str = None):
    color = color_override or score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={"text": title, "font": {"size": 18}},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color},
               "steps": [
                   {"range": [0, 25], "color": "#fee2e2"},
                   {"range": [25, 50], "color": "#fed7aa"},
                   {"range": [50, 75], "color": "#fef9c3"},
                   {"range": [75, 100], "color": "#dcfce7"},
               ]}
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def radar_chart(scores: dict, name: str = ""):
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    values = [scores[d]["score"] for d in DIMENSIONS]
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]
    fig = go.Figure(go.Scatterpolar(
        r=values_closed, theta=labels_closed, fill="toself", name=name,
        line=dict(color="#6366f1", width=2),
        fillcolor="rgba(99, 102, 241, 0.25)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, height=320, margin=dict(l=40, r=40, t=20, b=20),
    )
    return fig


def team_compare_radar(wildcats_agg: dict, spartans_agg: dict):
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    w = [wildcats_agg[d]["score"] for d in DIMENSIONS]
    s = [spartans_agg[d]["score"] for d in DIMENSIONS]
    labels_c = labels + [labels[0]]
    w_c = w + [w[0]]
    s_c = s + [s[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=w_c, theta=labels_c, fill="toself", name="Wildcats",
                                  line=dict(color="#ef4444", width=2),
                                  fillcolor="rgba(239, 68, 68, 0.2)"))
    fig.add_trace(go.Scatterpolar(r=s_c, theta=labels_c, fill="toself", name="Spartans",
                                  line=dict(color="#22c55e", width=2),
                                  fillcolor="rgba(34, 197, 94, 0.2)"))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True, height=380, margin=dict(l=40, r=40, t=20, b=20),
    )
    return fig


def player_distribution_chart(player_results: list, title: str, color: str):
    names = [r["_player"] for r in player_results]
    scores = [r["overall_stability_index"] for r in player_results]
    # Sort ascending so lowest stability is visible at top
    pairs = sorted(zip(names, scores), key=lambda x: x[1])
    names, scores = zip(*pairs)
    fig = go.Figure(go.Bar(
        x=list(scores), y=list(names), orientation="h",
        marker_color=[score_color(s) for s in scores],
        text=list(scores), textposition="outside",
    ))
    fig.update_layout(
        title=title, xaxis=dict(range=[0, 110], title="Stability index"),
        height=max(300, 28 * len(names)), margin=dict(l=20, r=20, t=40, b=40),
        showlegend=False,
    )
    return fig


# ---------- UI ----------
st.title("🧠 Athlete Cognitive Stability Analyzer")
st.caption(
    "Cross-references psychological signal from athlete communication against "
    "market-implied success probability."
)

st.info(
    "**Demo mode.** Athlete and roster feeds are pre-loaded simulated data; Polymarket odds are mocked. "
    "Psychological analysis runs live via GPT-4 when an API key is provided, otherwise serves "
    "cached results from prior runs.",
    icon="🎬",
)

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key (optional)", type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Leave blank to use cached results. Provide a key to run live analysis.",
    )
    model = st.selectbox("Model", ["gpt-4o", "gpt-4-turbo", "gpt-4"], index=0)

    if api_key and OPENAI_AVAILABLE:
        st.success("Live analysis available")
    elif api_key and not OPENAI_AVAILABLE:
        st.warning("openai package not installed — using cache")
    else:
        st.info("Using cached results")

    st.divider()
    st.markdown(
        "**Disclaimer:** Outputs are a research signal generated by an LLM "
        "reading text. Not financial advice. Not a validated predictor of "
        "athletic or team performance."
    )

athlete_key = st.selectbox(
    "Live monitor — select target",
    options=list(DEMO_FEEDS.keys()),
    index=0,
)
feed = DEMO_FEEDS[athlete_key]
is_team = feed.get("type") == "team"

# Feed display
with st.expander(
    "📡 Last 48hr ingested feed"
    + (f" — {len(feed['wildcats']) + len(feed['spartans'])} players across 2 rosters" if is_team else ""),
    expanded=False,
):
    if is_team:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Wildcats")
            for p in feed["wildcats"]:
                st.markdown(f"**{p['player']}**")
                for item in p["items"]:
                    st.caption(item["source"])
                    st.write(item["text"])
                st.divider()
        with c2:
            st.markdown("### Spartans")
            for p in feed["spartans"]:
                st.markdown(f"**{p['player']}**")
                for item in p["items"]:
                    st.caption(item["source"])
                    st.write(item["text"])
                st.divider()
    else:
        for item in feed["items"]:
            st.markdown(f"**{item['source']}**")
            st.write(item["text"])
            st.divider()

button_label = "Run roster analysis (24 players)" if is_team else "Run analysis"
analyze_clicked = st.button(button_label, type="primary", use_container_width=True)

if analyze_clicked:
    with st.spinner("Analyzing..."):
        result, source = analyze(athlete_key, feed, api_key, model)
        if result is not None:
            market = mock_polymarket_odds(athlete_key)
            st.session_state["result"] = result
            st.session_state["market"] = market
            st.session_state["athlete"] = athlete_key
            st.session_state["source"] = source
            st.session_state["is_team"] = is_team

# ---------- Dashboard ----------
if "result" in st.session_state and st.session_state.get("athlete") == athlete_key:
    result = st.session_state["result"]
    market = st.session_state["market"]
    source = st.session_state.get("source", "cached")
    showing_team = st.session_state.get("is_team", False)

    st.divider()
    source_label = "🟢 Live GPT-4 analysis" if source == "live" else f"💾 Cached result ({source})"
    st.caption(source_label)

    if showing_team:
        wildcats_agg = result["wildcats"]["aggregate"]
        spartans_agg = result["spartans"]["aggregate"]
        wildcats_stability = wildcats_agg["overall_stability_index"]
        spartans_stability = spartans_agg["overall_stability_index"]
        market_prob = market["implied_probability"]

        # Signal is computed against Wildcats stability (Wildcats moneyline prop)
        signal = divergence_signal(market_prob, wildcats_stability)

        st.markdown(
            f"""
            <div style="background-color: {signal['color']}; color: white;
                        padding: 18px 24px; border-radius: 8px; margin-bottom: 16px;">
                <div style="font-size: 13px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px;">
                    Divergence Signal · {feed['prop_market']}
                </div>
                <div style="font-size: 28px; font-weight: 700; margin-top: 4px;">
                    {signal['level']} &nbsp;·&nbsp; Δ = {signal['delta']:+.1f} pts
                </div>
                <div style="font-size: 14px; margin-top: 8px; opacity: 0.95;">
                    {signal['action']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Three-up: market, wildcats, spartans
        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(gauge_chart(market_prob, "Polymarket: Wildcats Win", color_override="#3b82f6"),
                            use_container_width=True)
            st.caption(f"Yes: {market['yes_price']} · 24h vol: ${market['volume_24h_usd']:,}")
        with c2:
            st.plotly_chart(gauge_chart(wildcats_stability, "Wildcats Aggregate Stability"),
                            use_container_width=True)
            st.caption(f"Mean across {len(result['wildcats']['player_results'])} players")
        with c3:
            st.plotly_chart(gauge_chart(spartans_stability, "Spartans Aggregate Stability"),
                            use_container_width=True)
            st.caption(f"Mean across {len(result['spartans']['player_results'])} players")

        st.subheader("Roster dimension comparison")
        st.plotly_chart(team_compare_radar(wildcats_agg, spartans_agg), use_container_width=True)

        st.subheader("Per-player breakdown")
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.plotly_chart(
                player_distribution_chart(result["wildcats"]["player_results"], "Wildcats — by player", "#ef4444"),
                use_container_width=True,
            )
        with pcol2:
            st.plotly_chart(
                player_distribution_chart(result["spartans"]["player_results"], "Spartans — by player", "#22c55e"),
                use_container_width=True,
            )

        # Roster summaries
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("**Wildcats aggregate summary**")
            st.write(wildcats_agg["summary"])
        with sc2:
            st.markdown("**Spartans aggregate summary**")
            st.write(spartans_agg["summary"])

        with st.expander("Per-player justifications"):
            tab1, tab2 = st.tabs(["Wildcats", "Spartans"])
            for tab, results_list in [(tab1, result["wildcats"]["player_results"]),
                                       (tab2, result["spartans"]["player_results"])]:
                with tab:
                    for r in sorted(results_list, key=lambda x: x["overall_stability_index"]):
                        st.markdown(f"**{r['_player']} — {r['overall_stability_index']}/100**")
                        st.caption(r.get("summary", ""))
                        st.write("")

        with st.expander("Raw JSON (copy to populate TEAM_ANALYSIS_CACHE)"):
            st.json({"team_result": result, "market": market, "divergence": signal})

    else:
        # Individual athlete dashboard (unchanged from v3)
        stability = result.get("overall_stability_index", 0)
        market_prob = market["implied_probability"]
        signal = divergence_signal(market_prob, stability)

        st.markdown(
            f"""
            <div style="background-color: {signal['color']}; color: white;
                        padding: 18px 24px; border-radius: 8px; margin-bottom: 16px;">
                <div style="font-size: 13px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px;">
                    Divergence Signal · {feed['prop_market']}
                </div>
                <div style="font-size: 28px; font-weight: 700; margin-top: 4px;">
                    {signal['level']} &nbsp;·&nbsp; Δ = {signal['delta']:+.1f} pts
                </div>
                <div style="font-size: 14px; margin-top: 8px; opacity: 0.95;">
                    {signal['action']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(gauge_chart(market_prob, "Polymarket Implied Probability", color_override="#3b82f6"),
                            use_container_width=True)
            st.caption(f"Yes: {market['yes_price']} · No: {market['no_price']} · "
                       f"24h volume: ${market['volume_24h_usd']:,} · {market['source']}")
        with c2:
            st.plotly_chart(gauge_chart(stability, "Cognitive Stability Index"),
                            use_container_width=True)
            st.caption("Derived from LLM analysis of 48hr communication feed.")

        st.subheader("Psychological dimension breakdown")
        rcol, mcol = st.columns([1, 1])
        with rcol:
            st.plotly_chart(radar_chart(result), use_container_width=True)
        with mcol:
            for d in DIMENSIONS:
                st.metric(DIMENSION_LABELS[d], f"{result[d]['score']}/100")

        with st.expander("Dimension justifications"):
            for d in DIMENSIONS:
                st.markdown(f"**{DIMENSION_LABELS[d]} — {result[d]['score']}/100**")
                st.write(result[d]["justification"])
                st.write("")

        st.subheader("Analyst summary")
        st.write(result.get("summary", ""))
        signals = result.get("key_signals", [])
        if signals:
            st.markdown("**Key signals:** " + " · ".join(signals))

        with st.expander("Raw JSON (copy to populate ANALYSIS_CACHE)"):
            st.json({"psychological": result, "market": market, "divergence": signal})

    st.divider()
    st.caption(
        "⚠️ Research output only. The cognitive stability index is an LLM-derived "
        "signal from public text and has not been validated as a predictor of "
        "athletic or team outcomes. Polymarket odds shown here are mocked for demonstration. "
        "Nothing in this app is financial advice."
    )
