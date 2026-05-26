"""
Athlete Cognitive Stability Analyzer
Analyzes press conference transcripts and social media posts using GPT-4
to produce a cognitive stability score across four dimensions.
"""

import json
import os
import streamlit as st
from openai import OpenAI
import plotly.graph_objects as go
import plotly.express as px

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

DIMENSION_HELP = {
    "emotional_regulation": (
        "Ability to manage and modulate emotional responses. "
        "Higher = composed, measured language. Lower = volatile, reactive."
    ),
    "cognitive_load": (
        "Mental processing demand evident in the text. "
        "Higher = clear, organized thought. Lower = scattered, overwhelmed."
    ),
    "risk_assessment": (
        "Quality of judgment about risks and consequences. "
        "Higher = balanced perspective. Lower = impulsive or distorted."
    ),
    "stress_indicators": (
        "Absence of stress markers in language. "
        "Higher = relaxed, confident. Lower = pressured, anxious."
    ),
}

ANALYSIS_PROMPT = """You are a sports psychology analyst evaluating athlete communication for cognitive stability. Analyze the following text across four dimensions. For each dimension, provide a score from 0 to 100 (where 100 = optimal stability) and a brief justification.

Dimensions:
1. emotional_regulation: How well the athlete modulates emotional responses. Look for composure, measured language, ability to discuss setbacks without volatility. Low scores: reactive outbursts, blame, extreme language.
2. cognitive_load: Mental clarity and organization of thought. Look for coherent reasoning, clear focus. Low scores: scattered statements, contradictions, signs of being overwhelmed.
3. risk_assessment: Quality of judgment about risks, consequences, and self-awareness. Look for balanced perspective, realistic appraisal. Low scores: impulsive declarations, distorted thinking, denial.
4. stress_indicators: Absence of acute stress markers. Look for relaxed phrasing, confidence. Low scores: pressured speech, anxiety markers, defensive posture, hedging under duress.

Return ONLY valid JSON in this exact schema, no markdown fences:
{
  "emotional_regulation": {"score": <int 0-100>, "justification": "<one sentence>"},
  "cognitive_load": {"score": <int 0-100>, "justification": "<one sentence>"},
  "risk_assessment": {"score": <int 0-100>, "justification": "<one sentence>"},
  "stress_indicators": {"score": <int 0-100>, "justification": "<one sentence>"},
  "overall_stability_index": <int 0-100>,
  "summary": "<2-3 sentence overall read>",
  "key_signals": ["<short phrase>", "<short phrase>", "<short phrase>"]
}

The overall_stability_index should be a weighted synthesis (not just the mean) reflecting your holistic judgment.

TEXT TO ANALYZE:
---
{text}
---
"""


# ---------- API call ----------
def analyze_text(text: str, api_key: str, model: str = "gpt-4o") -> dict:
    """Send text to OpenAI and parse the structured response."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a precise sports psychology analyst. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": ANALYSIS_PROMPT.replace("{text}", text),
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


# ---------- Visualizations ----------
def score_color(score: int) -> str:
    """Map a 0-100 score to a color."""
    if score >= 75:
        return "#22c55e"  # green
    if score >= 50:
        return "#eab308"  # yellow
    if score >= 25:
        return "#f97316"  # orange
    return "#ef4444"  # red


def gauge_chart(score: int, title: str = "Overall Stability Index") -> go.Figure:
    """Big gauge for the overall index."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": title, "font": {"size": 20}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": score_color(score)},
                "steps": [
                    {"range": [0, 25], "color": "#fee2e2"},
                    {"range": [25, 50], "color": "#fed7aa"},
                    {"range": [50, 75], "color": "#fef9c3"},
                    {"range": [75, 100], "color": "#dcfce7"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def radar_chart(scores: dict) -> go.Figure:
    """Radar across the four dimensions."""
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    values = [scores[d]["score"] for d in DIMENSIONS]
    # Close the loop
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            line=dict(color="#6366f1", width=2),
            fillcolor="rgba(99, 102, 241, 0.25)",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=350,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    return fig


def bar_chart(scores: dict) -> go.Figure:
    """Horizontal bar of dimension scores."""
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    values = [scores[d]["score"] for d in DIMENSIONS]
    colors = [score_color(v) for v in values]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=values,
            textposition="outside",
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 110], title="Score"),
        height=300,
        margin=dict(l=20, r=20, t=20, b=40),
        showlegend=False,
    )
    return fig


# ---------- UI ----------
st.title("🧠 Athlete Cognitive Stability Analyzer")
st.caption(
    "Paste a press conference transcript or social media post. "
    "GPT-4 will score it across four cognitive dimensions."
)

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Stored only in session memory.",
    )
    model = st.selectbox(
        "Model",
        ["gpt-4o", "gpt-4-turbo", "gpt-4"],
        index=0,
    )
    st.divider()
    st.markdown("**Dimensions**")
    for d in DIMENSIONS:
        st.markdown(f"**{DIMENSION_LABELS[d]}**  \n{DIMENSION_HELP[d]}")

# Sample text for quick testing
SAMPLE = (
    "Look, I don't care what anyone says. The refs were against us tonight, the league has been "
    "against me my whole career, and honestly nobody in that locker room played for me. I'm done "
    "talking about this. Next question. Actually, you know what, no — write whatever you want, "
    "it doesn't matter anymore."
)

col_input, col_actions = st.columns([4, 1])
with col_input:
    text_input = st.text_area(
        "Text to analyze",
        height=200,
        placeholder="Paste transcript or post here...",
    )
with col_actions:
    st.write("")
    st.write("")
    if st.button("Load sample", use_container_width=True):
        st.session_state["sample_loaded"] = SAMPLE
        st.rerun()

if "sample_loaded" in st.session_state and not text_input:
    text_input = st.session_state["sample_loaded"]
    st.info("Sample loaded — click Analyze.")

analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

# ---------- Analysis ----------
if analyze_clicked:
    if not api_key:
        st.error("Add your OpenAI API key in the sidebar.")
    elif not text_input.strip():
        st.error("Paste some text first.")
    else:
        with st.spinner("Analyzing..."):
            try:
                result = analyze_text(text_input, api_key, model)
                st.session_state["last_result"] = result
                st.session_state["last_text"] = text_input
            except json.JSONDecodeError:
                st.error("Model returned invalid JSON. Try again.")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

# ---------- Dashboard ----------
if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    overall = result.get("overall_stability_index", 0)

    st.divider()
    st.subheader("Results")

    top_left, top_right = st.columns([1, 1])
    with top_left:
        st.plotly_chart(gauge_chart(overall), use_container_width=True)
    with top_right:
        st.plotly_chart(radar_chart(result), use_container_width=True)

    # Metric strip
    cols = st.columns(4)
    for col, d in zip(cols, DIMENSIONS):
        score = result[d]["score"]
        col.metric(DIMENSION_LABELS[d], f"{score}/100")

    st.plotly_chart(bar_chart(result), use_container_width=True)

    # Justifications
    st.subheader("Dimension breakdown")
    for d in DIMENSIONS:
        with st.expander(f"{DIMENSION_LABELS[d]} — {result[d]['score']}/100"):
            st.write(result[d]["justification"])

    # Summary + signals
    st.subheader("Summary")
    st.write(result.get("summary", ""))

    signals = result.get("key_signals", [])
    if signals:
        st.subheader("Key signals")
        st.markdown("\n".join(f"- {s}" for s in signals))

    # Raw JSON
    with st.expander("Raw JSON output"):
        st.json(result)

    # Download
    st.download_button(
        "Download report (JSON)",
        data=json.dumps(
            {"input_text": st.session_state["last_text"], "analysis": result},
            indent=2,
        ),
        file_name="cognitive_stability_report.json",
        mime="application/json",
    )
