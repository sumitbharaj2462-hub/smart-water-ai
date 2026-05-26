"""
AquaOps AI Assistant — LLM-powered operations chat for administrators.

Run: streamlit run dashboard_assistant.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from assistant.agent import WaterAssistantAgent
from assistant.config import OPENAI_API_KEY, REPORTS_DIR
from assistant.reports.emergency import generate_emergency_report

st.set_page_config(
    page_title="AquaOps AI Assistant",
    page_icon="💧",
    layout="wide",
)

st.info("**Tip:** All modules are in the unified app → run `streamlit run dashboard.py` and choose **AI Assistant** in the sidebar.")
st.title("AquaOps AI Assistant")
st.caption("Operational Q&A · shortage summaries · prediction explanations · emergency reports")

if "agent" not in st.session_state:
    st.session_state.agent = WaterAssistantAgent()
if "messages" not in st.session_state:
    st.session_state.messages = []

agent: WaterAssistantAgent = st.session_state.agent

# Sidebar
with st.sidebar:
    st.header("Assistant settings")
    st.write(f"**Provider:** {agent.provider_info()}")
    if OPENAI_API_KEY:
        st.success("OpenAI API key configured")
    else:
        st.info(
            "Running local analyst mode. Set `OPENAI_API_KEY` for full LLM reasoning.\n\n"
            "Or use Ollama: `OLLAMA_BASE_URL=http://localhost:11434/v1`"
        )

    if st.button("Refresh platform data"):
        agent.refresh_context()
        st.success("Context updated")

    st.divider()
    st.subheader("Quick actions")
    if st.button("Summarize shortages"):
        st.session_state.messages.append({"role": "user", "content": "Summarize water shortages across all zones"})
        _r = agent.chat("Summarize water shortages across all zones", st.session_state.messages[:-1])
        st.session_state.messages.append({"role": "assistant", "content": _r["content"]})
        st.rerun()

    if st.button("Analytics briefing"):
        st.session_state.messages.append({"role": "user", "content": "Give me an analytics overview for administrators"})
        _r = agent.chat("Give me an analytics overview for administrators", st.session_state.messages[:-1])
        st.session_state.messages.append({"role": "assistant", "content": _r["content"]})
        st.rerun()

    if st.button("Generate emergency report"):
        report = generate_emergency_report(save=True)
        st.session_state.messages.append(
            {"role": "user", "content": "Generate an emergency report"}
        )
        st.session_state.messages.append({"role": "assistant", "content": report})
        st.rerun()

    st.divider()
    st.subheader("Example questions")
    examples = [
        "Which zones have the highest water risk?",
        "Explain the 7-day demand forecast for Central Delhi",
        "How should we deploy tankers today?",
        "What anomalies were detected recently?",
        "Compare LSTM, GRU and Transformer model accuracy",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:20]}"):
            st.session_state.messages.append({"role": "user", "content": ex})
            hist = st.session_state.messages[:-1]
            resp = agent.chat(ex, hist)
            st.session_state.messages.append(
                {"role": "assistant", "content": resp["content"], "meta": resp}
            )
            st.rerun()

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

# Main chat
col_chat, col_ctx = st.columns([2, 1])

with col_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                m = msg["meta"]
                st.caption(f"via {m.get('provider', '?')} / {m.get('model', '?')}")

    if prompt := st.chat_input("Ask about supply, demand, forecasts, routes, or emergencies..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
            if m["role"] in ("user", "assistant")
        ]
        with st.chat_message("assistant"):
            with st.spinner("Analyzing platform data..."):
                result = agent.chat(prompt, history)
            st.markdown(result["content"])
            st.caption(f"via {result.get('provider')} / {result.get('model')}")
        st.session_state.messages.append(
            {"role": "assistant", "content": result["content"], "meta": result}
        )

with col_ctx:
    st.subheader("Live platform context")
    snap = agent.snapshot
    st.metric("Zones", len(snap.get("zones", [])))
    risks = snap.get("zone_risks", [])
    if risks and "error" not in risks[0]:
        avg_risk = sum(r.get("risk_score", 0) for r in risks) / len(risks)
        critical = sum(1 for r in risks if r.get("risk_level") in ("critical", "high"))
        st.metric("Avg risk %", f"{avg_risk:.1f}")
        st.metric("Elevated zones", critical)
    st.metric("IoT API", snap.get("iot_status", {}).get("telemetry_api", "?"))
    st.caption(f"Snapshot: {snap.get('generated_at', '')[:19]}")

    with st.expander("Zone risks"):
        if risks:
            import pandas as pd

            st.dataframe(
                pd.DataFrame(risks)[
                    ["zone", "risk_score", "risk_level", "gap_liters"]
                ],
                hide_index=True,
                use_container_width=True,
            )

    with st.expander("Saved emergency reports"):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        reports = sorted(REPORTS_DIR.glob("emergency_*.md"), reverse=True)[:5]
        for rp in reports:
            st.text(rp.name)

# Download last report
reports = sorted(Path(REPORTS_DIR).glob("emergency_*.md"), reverse=True) if REPORTS_DIR.exists() else []
if reports:
    st.sidebar.download_button(
        "Download latest emergency report",
        reports[0].read_text(encoding="utf-8"),
        file_name=reports[0].name,
        mime="text/markdown",
    )
