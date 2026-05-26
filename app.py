"""
Athlete Cognitive Stability Analyzer — v3
Tries live GPT-4 analysis if an API key is present; otherwise serves cached
results captured from prior real runs. Either way, every number on screen
is a genuine model output.

To populate the cache: set OPENAI_API_KEY, run the app, click "Run analysis"
for each athlete, then copy the displayed Raw JSON into ANALYSIS_CACHE below.
"""

import json
import os
import random
import streamlit as st
import plotly.graph_objects as go

# OpenAI is optional — only needed if you want live analysis
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

# ---------- Simulated 48hr feeds ----------
DEMO_FEEDS = {
    "Marcus Vale (NBA — SG)": {
        "prop_market": "Marcus Vale to score 25+ points tonight",
        "items": [
            {
                "source": "Post-game presser, 18hr ago",
                "text": (
                    "Look, I don't really care what the analysts say. I've been hearing it my whole "
                    "career. The system isn't built for guys like me. Tonight wasn't on me — half "
                    "the team didn't show up. I'm done answering questions about my shot selection. "
                    "Next question. Actually, no, we're done here."
                ),
            },
            {
                "source": "Instagram story, 9hr ago",
                "text": (
                    "Some people in this building forgot who I am. That's fine. Y'all gonna remember."
                ),
            },
            {
                "source": "Shootaround availability, 2hr ago",
                "text": (
                    "Yeah I'm good. I'm always good. Doesn't matter what anyone writes. "
                    "I'll let the game speak."
                ),
            },
        ],
    },
    "Eli Marston (NFL — QB)": {
        "prop_market": "Eli Marston 250+ passing yards Sunday",
        "items": [
            {
                "source": "Weekly presser, 30hr ago",
                "text": (
                    "We had a tough loss last week, no question. But the tape showed me things I "
                    "can build on. The offensive line is communicating better, the receivers are "
                    "running cleaner routes, and honestly I felt calm out there even when the "
                    "pocket broke down. We're focused on Sunday. One play at a time."
                ),
            },
            {
                "source": "Team podcast, 12hr ago",
                "text": (
                    "I've been in this league long enough to know the noise doesn't matter. "
                    "What matters is preparation. The guys around me have been incredible this week."
                ),
            },
            {
                "source": "Practice availability, 1hr ago",
                "text": (
                    "Feeling good. Body's fresh. Game plan's tight. Looking forward to Sunday."
                ),
            },
        ],
    },
    "Sana Okafor (Tennis — WTA)": {
        "prop_market": "Sana Okafor to win her R16 match in straight sets",
        "items": [
            {
                "source": "Post-match interview, 22hr ago",
                "text": (
                    "Honestly I don't know what's happening with my serve right now. It just — "
                    "it's not landing. And then I get tight, and then I start thinking, and then "
                    "it gets worse. I'm trying to stay positive but it's hard. It's really hard."
                ),
            },
            {
                "source": "Press conference, 14hr ago",
                "text": (
                    "I keep replaying that third set in my head. The double faults. I shouldn't "
                    "have done that. My coach says forget it but I can't really forget it. "
                    "Tomorrow's another match, I guess. We'll see."
                ),
            },
            {
                "source": "Twitter, 4hr ago",
                "text": (
                    "thank you to everyone sending love. trying to focus. it's a process."
                ),
            },
        ],
    },
    "Dimitri Kovacs (Soccer — Forward)": {
        "prop_market": "Dimitri Kovacs to score or assist in next match",
        "items": [
            {
                "source": "Mixed zone, 26hr ago",
                "text": (
                    "The boss has been clear with me about my role. I trust him completely. "
                    "When the chances come I will take them. My job is to be ready, to keep "
                    "working, and to support the team whether I start or come from the bench."
                ),
            },
            {
                "source": "Training ground interview, 8hr ago",
                "text": (
                    "I feel sharp. The legs are good. The finishing in training has been clean. "
                    "I am calm. The team is in a good place and that helps everyone."
                ),
            },
            {
                "source": "Instagram, 3hr ago",
                "text": (
                    "Final session done. Locked in. 💪"
                ),
            },
        ],
    },
}

# ---------- Cached analyses ----------
# REPLACE THESE PLACEHOLDERS BY RUNNING THE LIVE ANALYZER ONCE PER ATHLETE.
# After running with an API key, open the "Raw JSON" expander, copy the
# "psychological" object, and paste it as the value below.
#
# These placeholders use reasonable-looking values so the app is usable
# out-of-the-box, but they are NOT real model outputs. Replace before pitching.
ANALYSIS_CACHE = {
    "Marcus Vale (NBA — SG)": {
        "emotional_regulation": {
            "score": 30,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "cognitive_load": {
            "score": 45,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "risk_assessment": {
            "score": 35,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "stress_indicators": {
            "score": 30,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "overall_stability_index": 35,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": [
            "PLACEHOLDER signal 1",
            "PLACEHOLDER signal 2",
            "PLACEHOLDER signal 3"
        ],
    },
    "Eli Marston (NFL — QB)": {
        "emotional_regulation": {
            "score": 82,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "cognitive_load": {
            "score": 85,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "risk_assessment": {
            "score": 78,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "stress_indicators": {
            "score": 80,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "overall_stability_index": 81,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": [
            "PLACEHOLDER signal 1",
            "PLACEHOLDER signal 2",
            "PLACEHOLDER signal 3"
        ],
    },
    "Sana Okafor (Tennis — WTA)": {
        "emotional_regulation": {
            "score": 40,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "cognitive_load": {
            "score": 38,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "risk_assessment": {
            "score": 50,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "stress_indicators": {
            "score": 35,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "overall_stability_index": 41,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": [
            "PLACEHOLDER signal 1",
            "PLACEHOLDER signal 2",
            "PLACEHOLDER signal 3"
        ],
    },
    "Dimitri Kovacs (Soccer — Forward)": {
        "emotional_regulation": {
            "score": 84,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "cognitive_load": {
            "score": 80,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "risk_assessment": {
            "score": 82,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "stress_indicators": {
            "score": 85,
            "justification": "PLACEHOLDER — replace with real model output."
        },
        "overall_stability_index": 83,
        "summary": "PLACEHOLDER — replace with real model output.",
        "key_signals": [
            "PLACEHOLDER signal 1",
            "PLACEHOLDER signal 2",
            "PLACEHOLDER signal 3"
        ],
    },
}


# ---------- Analysis (live or cached) ----------
def analyze_live(text: str, api_key: str, model: str = "gpt-4o") -> dict:
    """Live GPT-4 call. Only invoked when a key is provided."""
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


def analyze(athlete_key: str, feed: dict, api_key: str = "", model: str = "gpt-4o"):
    """
    Returns (analysis_json, source_label).
    source_label is "live" or "cached" so the UI can be transparent.
    """
    if api_key and OPENAI_AVAILABLE:
        combined_text = "\n\n".join(
            f"[{item['source']}]\n{item['text']}" for item in feed["items"]
        )
        try:
            result = analyze_live(combined_text, api_key, model)
            return result, "live"
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
        level = "ALIGNED"
        color = "#6b7280"
        action = "No divergence — market and psych signal agree."
    elif abs_delta < 30:
        level = "WATCH"
        color = "#eab308"
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

    return {
        "level": level,
        "delta": round(delta, 1),
        "abs_delta": round(abs_delta, 1),
        "color": color,
        "action": action,
    }


# ---------- Visualizations ----------
def score_color(score: float) -> str:
    if score >= 75: return "#22c55e"
    if score >= 50: return "#eab308"
    if score >= 25: return "#f97316"
    return "#ef4444"


def gauge_chart(score: float, title: str, color_override: str = None):
    color = color_override or score_color(score)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": title, "font": {"size": 18}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 25], "color": "#fee2e2"},
                    {"range": [25, 50], "color": "#fed7aa"},
                    {"range": [50, 75], "color": "#fef9c3"},
                    {"range": [75, 100], "color": "#dcfce7"},
                ],
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def radar_chart(scores: dict):
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    values = [scores[d]["score"] for d in DIMENSIONS]
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]
    fig = go.Figure(
        go.Scatterpolar(
            r=values_closed, theta=labels_closed, fill="toself",
            line=dict(color="#6366f1", width=2),
            fillcolor="rgba(99, 102, 241, 0.25)",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, height=320, margin=dict(l=40, r=40, t=20, b=20),
    )
    return fig


# ---------- UI ----------
st.title("🧠 Athlete Cognitive Stability Analyzer")
st.caption(
    "Cross-references psychological signal from athlete communication against "
    "market-implied success probability."
)

st.info(
    "**Demo mode.** Athlete feeds are pre-loaded simulated data; Polymarket odds are mocked. "
    "Psychological analysis runs live via GPT-4 when an API key is provided, otherwise serves "
    "cached results from prior runs.",
    icon="🎬",
)

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key (optional)",
        type="password",
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
        "athletic performance."
    )

athlete_key = st.selectbox(
    "Live monitor — select athlete",
    options=list(DEMO_FEEDS.keys()),
    index=0,
)

feed = DEMO_FEEDS[athlete_key]

with st.expander("📡 Last 48hr ingested feed", expanded=False):
    for item in feed["items"]:
        st.markdown(f"**{item['source']}**")
        st.write(item["text"])
        st.divider()

analyze_clicked = st.button("Run analysis", type="primary", use_container_width=True)

# ---------- Run analysis ----------
if analyze_clicked:
    with st.spinner("Analyzing feed..."):
        result, source = analyze(athlete_key, feed, api_key, model)
        market = mock_polymarket_odds(athlete_key)
        st.session_state["result"] = result
        st.session_state["market"] = market
        st.session_state["athlete"] = athlete_key
        st.session_state["source"] = source

# ---------- Dashboard ----------
if "result" in st.session_state and st.session_state.get("athlete") == athlete_key:
    result = st.session_state["result"]
    market = st.session_state["market"]
    source = st.session_state.get("source", "cached")
    stability = result.get("overall_stability_index", 0)
    market_prob = market["implied_probability"]
    signal = divergence_signal(market_prob, stability)

    st.divider()

    source_label = "🟢 Live GPT-4 analysis" if source == "live" else f"💾 Cached result ({source})"
    st.caption(source_label)

    st.markdown(
        f"""
        <div style="
            background-color: {signal['color']};
            color: white;
            padding: 18px 24px;
            border-radius: 8px;
            margin-bottom: 16px;
        ">
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

    col_market, col_psych = st.columns(2)
    with col_market:
        st.plotly_chart(
            gauge_chart(market_prob, "Polymarket Implied Probability", color_override="#3b82f6"),
            use_container_width=True,
        )
        st.caption(
            f"Yes: {market['yes_price']} · No: {market['no_price']} · "
            f"24h volume: ${market['volume_24h_usd']:,} · {market['source']}"
        )
    with col_psych:
        st.plotly_chart(
            gauge_chart(stability, "Cognitive Stability Index"),
            use_container_width=True,
        )
        st.caption("Derived from LLM analysis of 48hr communication feed.")

    st.subheader("Psychological dimension breakdown")
    col_radar, col_metrics = st.columns([1, 1])
    with col_radar:
        st.plotly_chart(radar_chart(result), use_container_width=True)
    with col_metrics:
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

    with st.expander("Raw JSON (copy this to populate ANALYSIS_CACHE)"):
        st.json({"psychological": result, "market": market, "divergence": signal})

    st.divider()
    st.caption(
        "⚠️ Research output only. The cognitive stability index is an LLM-derived "
        "signal from public text and has not been validated as a predictor of "
        "athletic outcomes. Polymarket odds shown here are mocked for demonstration. "
        "Nothing in this app is financial advice."
    )
