'''
Streamlit UI for the Brand Guardian video compliance audit pipeline.

Run with:  uv run streamlit run streamlit_app.py
'''

import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app as audit_graph

st.set_page_config(page_title="Brand Guardian", layout="wide")

SEVERITY_ICONS = {"CRITICAL": "🔴", "WARNING": "🟠"}
NODE_LABELS = {
    "indexer": "Indexing video (download, upload to Azure Video Indexer, extract transcript & OCR)",
    "auditor": "Auditing content (retrieve rules, query LLM)",
}
# state keys that accumulate across nodes (operator.add reducers in VideoAuditState)
LIST_KEYS = ("compliance_results", "errors")


def merge_update(state: dict, update: dict) -> None:
    '''Apply a node's partial state update the same way LangGraph does.'''
    for key, value in update.items():
        if key in LIST_KEYS:
            state[key] = state.get(key, []) + (value or [])
        else:
            state[key] = value


def run_audit(video_url: str) -> dict:
    session_id = str(uuid.uuid4())
    state = {
        "video_url": video_url,
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": [],
    }

    with st.status("Running audit...", expanded=True) as status:
        st.write(NODE_LABELS["indexer"])
        for chunk in audit_graph.stream(state, stream_mode="updates"):
            for node, update in chunk.items():
                merge_update(state, update or {})
                st.write(f"Finished: {node}")
                if node == "indexer":
                    st.write(NODE_LABELS["auditor"])
        status.update(label="Audit complete", state="complete", expanded=False)

    return state


def render_report(state: dict) -> None:
    errors = state.get("errors", [])
    results = state.get("compliance_results", [])
    final_status = state.get("final_status", "UNKNOWN")

    st.divider()
    st.subheader("Compliance Audit Report")

    col1, col2, col3 = st.columns(3)
    col1.metric("Video ID", state.get("video_id", "-"))
    col2.metric("Status", final_status)
    col3.metric("Violations", len(results))

    # system errors (e.g. video processing failed) are not compliance verdicts
    if errors:
        st.error("The audit could not complete normally.")
        for err in errors:
            st.code(err, language=None)
    elif final_status == "PASS":
        st.success("No compliance violations detected.")
    else:
        st.warning("Compliance violations detected.")

    if results:
        st.markdown("#### Violations")
        for issue in results:
            severity = str(issue.get("severity", "")).upper()
            icon = SEVERITY_ICONS.get(severity, "⚪")
            with st.container(border=True):
                st.markdown(f"{icon} **{issue.get('category', 'Uncategorized')}** — `{severity or 'UNKNOWN'}`")
                st.write(issue.get("description", ""))

    st.markdown("#### Summary")
    st.write(state.get("final_report") or "No report generated.")

    with st.expander("Transcript"):
        st.write(state.get("transcript") or "No transcript available.")
    with st.expander("On-screen text (OCR)"):
        ocr = state.get("ocr_text") or []
        st.write("\n".join(f"- {line}" for line in ocr) if ocr else "No on-screen text detected.")
    with st.expander("Video metadata"):
        st.json(state.get("video_metadata") or {})


st.title("Brand Guardian")
st.caption("AI video compliance audit — Azure Video Indexer + Azure AI Search (RAG) + GPT-4o")

with st.form("audit_form"):
    video_url = st.text_input(
        "YouTube video URL",
        value="https://youtu.be/dT7S75eYhcQ",
        placeholder="https://www.youtube.com/watch?v=...",
    )
    submitted = st.form_submit_button("Run audit", type="primary")

if submitted:
    url = video_url.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        st.error("Please enter a valid YouTube URL.")
    else:
        try:
            st.session_state["report"] = run_audit(url)
        except Exception as e:
            st.session_state.pop("report", None)
            st.error(f"Workflow execution failed: {e}")

if "report" in st.session_state:
    render_report(st.session_state["report"])
