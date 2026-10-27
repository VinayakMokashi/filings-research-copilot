"""The copilot's web UI (step 6.3): a chat over the API and a page of evaluation results.

- **Ask:** questions stream through `POST /v1/ask`. While the copilot works, the current step
  shows ("Choosing who answers...", "Checking every cited sentence..."); then the answer,
  with how the question was read when it was a follow-up, the chart and table of a query's
  result, every source (a filing page opens in place, the facts database shows its SQL),
  the steps with their times, and thumbs up or down, kept through `POST /v1/feedback`.
- **Results:** the headline numbers of the evaluations, read from eval/results.

Run `poe ui` (Streamlit on 127.0.0.1:8501) while `poe api` serves the API; `FRC_API_URL`
points it elsewhere.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from copilot.api.client import STEPS, CopilotClient
from copilot.config import Settings
from copilot.eval.stats import exact_interval

API_URL = Settings().api_url
RESULTS = Path(__file__).resolve().parents[3] / "eval" / "results"
DATABASE = "facts-database"

EXAMPLES = (
    "What was 3M's capital expenditure in 2018?",
    "How did Boeing's revenue change from 2019 to 2022, and what drove the recovery?",
    "What risks does Netflix name in its 2022 10-K?",
    "Which companies do you cover?",
)
# (area, what, run folder under eval/results, metric)
HEADLINES = (
    ("Routing", "LLM router, held-out test split", "routing/llm-gpt-oss-120b/test", "accuracy"),
    (
        "Routing",
        "Semantic fallback, held-out test split",
        "routing/semantic-masked-centroid/test",
        "accuracy",
    ),
    (
        "Retrieval",
        "Recall@10 of the doc agent's search",
        "retrieval/page_bge-small-dense-rw-multi-hyde-decompose-understood/dev",
        "recall@10",
    ),
    (
        "Doc agent",
        "Correct on FinanceBench dev",
        "correctness/doc-agent-v4-full--qwen3.8-27b-p2/dev",
        "correct",
    ),
    (
        "Validator",
        "Faithful after the validator loop",
        "faithfulness/doc-agent-v4-validated--qwen3.8-27b-f1/dev",
        "faithful",
    ),
    (
        "Validator",
        "Correct after the validator loop",
        "correctness/doc-agent-v4-validated--qwen3.8-27b-p2/dev",
        "correct",
    ),
    ("Data agent", "SQL set, held-out test split", "sql/sql-agent-v2/test", "accuracy"),
    (
        "Data agent",
        "FinanceBench's metrics questions",
        "correctness/data-agent-v1--qwen3.8-27b-p2/dev",
        "correct",
    ),
    ("Hybrid answers", "Every expected figure, version 2", "hybrid/hybrid-v2/dev", "all_figures"),
    ("Memory", "Follow-ups and notes resolved", "memory/memory-v2/dev", "resolved"),
)


def plain(text: str) -> str:
    """Text for Markdown with its dollar signs kept: two of them would start a formula."""
    return text.replace("$", "\\$")


def client() -> CopilotClient:
    """The API, as this browser session's visitor."""
    if "visitor" not in st.session_state:
        st.session_state.visitor = uuid.uuid4().hex
    return CopilotClient(API_URL, st.session_state.visitor)


@st.cache_data(ttl=3600, show_spinner=False)
def page(doc_name: str, number: int) -> dict[str, Any] | None:
    return CopilotClient(API_URL, "ui-pages").source(doc_name, number)


def ask_page() -> None:
    state = st.session_state
    state.setdefault("turns", [])
    state.setdefault("thread", None)
    st.title("Filings Research Copilot")
    st.caption(
        "Questions about 40 public companies' SEC filings and reported figures, answered with "
        "a source for every sentence."
    )
    with st.sidebar:
        if st.button("New conversation", icon=":material/add_comment:", width="stretch"):
            state.turns, state.thread = [], None
        st.subheader("Try a question")
        for example in EXAMPLES:
            if st.button(example, key=f"example-{example}", width="stretch"):
                state.pending = example
        readiness = client().ready()
        if readiness.get("ready"):
            st.success("The copilot is ready.", icon=":material/check_circle:")
        else:
            failing = [name for name, ok in readiness.get("checks", {}).items() if not ok]
            st.warning("Not ready: " + (", ".join(failing) or "the API can't be reached"))
    for number, turn in enumerate(state.turns, start=1):
        show(number, turn)
    question = st.chat_input("Ask about a company's filings") or state.pop("pending", None)
    if question:
        state.turns.append(run(question))
        st.rerun()


def run(question: str) -> dict[str, Any]:
    """Ask the API, showing each step as it starts; the turn as the page keeps it."""
    state = st.session_state
    turn: dict[str, Any] = {"question": question, "events": [], "response": None, "error": None}
    with st.chat_message("user"):
        st.markdown(plain(question))
    with st.chat_message("assistant"), st.status("Working on it...") as status:
        for event in client().ask(question, state.thread):
            turn["events"].append({"kind": event.kind, **event.data})
            if event.kind == "meta":
                turn["meta"] = event.data
                state.thread = event.data.get("thread_id", state.thread)
            elif event.kind == "start":
                status.update(label=STEPS.get(event.data.get("node", ""), "Working") + "...")
            elif event.kind == "response":
                turn["response"] = event.data
            elif event.kind == "error":
                turn["error"] = event.data.get("error", "The copilot failed.")
        done = turn["response"] is not None
        status.update(label="Done" if done else "Stopped", state="complete" if done else "error")
    return turn


def show(number: int, turn: dict[str, Any]) -> None:
    """One exchange: the question, the answer and everything behind it."""
    with st.chat_message("user"):
        st.markdown(plain(turn["question"]))
    with st.chat_message("assistant"):
        response = turn["response"]
        if response is None:
            st.error(turn["error"] or "No answer came back.")
            return
        standalone = response.get("standalone")
        if standalone and standalone != turn["question"]:
            st.caption(f"Read as: {plain(standalone)}")
        st.markdown(plain(response.get("text") or "") or "_No answer._")
        notes = [
            "Served from the cache: this question was asked before."
            if response.get("cached")
            else "",
            handed_on(response),
            checked(response.get("validation") or {}),
            assessed(response),
        ]
        for note in filter(None, notes):
            st.caption(note)
        table = response.get("table")
        if table:
            show_table(table, response.get("chart"))
        show_sources(response)
        show_steps(turn["events"])
        rating = st.feedback("thumbs", key=f"feedback-{number}")
        if rating is not None and not turn.get("rated"):
            meta = turn.get("meta", {})
            kept = client().feedback(
                str(meta.get("thread_id", "")),
                int(response.get("turn", number)),
                "up" if rating == 1 else "down",
                meta.get("request_id"),
            )
            turn["rated"] = True
            st.toast("Thanks: your feedback is kept." if kept else "The feedback couldn't be kept.")


def handed_on(response: dict[str, Any]) -> str:
    if (response.get("handoff") or {}).get("from") != "data":
        return ""
    return "The facts database had nothing to answer this with; the filings' text answered it."


def assessed(response: dict[str, Any]) -> str:
    if "Assessment:" not in (response.get("text") or ""):
        return ""
    return "The assessment is the copilot's reading of the cited facts, not a statement in them."


def checked(validation: dict[str, Any]) -> str:
    if not validation.get("checked"):
        return ""
    revisions = int(validation.get("revisions", 0))
    if validation.get("faithful"):
        after = f", after {revisions} revision{'s' * (revisions != 1)}" if revisions else ""
        return f"Every cited sentence was checked against its source{after}."
    cut = len(validation.get("unverified") or [])
    return f"Checked against the sources: {cut} sentence{'s' * (cut != 1)} could not be verified."


def show_table(table: dict[str, Any], chart: dict[str, Any] | None) -> None:
    frame = pd.DataFrame(table["rows"], columns=table["columns"])
    kind, x, y = (chart or {}).get("kind"), (chart or {}).get("x"), (chart or {}).get("y")
    if kind == "metric" and y in frame and len(frame) == 1:
        st.metric(str(y).replace("_", " "), f"{frame[y].iloc[0]:,}")
    elif kind in ("bar", "line") and x in frame and y in frame:
        (st.bar_chart if kind == "bar" else st.line_chart)(frame, x=x, y=y)
    with st.expander("Query result"):
        st.dataframe(frame, hide_index=True)
        if table.get("truncated"):
            st.caption("The first 50 rows.")


def show_sources(response: dict[str, Any]) -> None:
    citations = sorted(response.get("citations") or [], key=lambda c: int(c.get("number", 0)))
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)})"):
        for citation in citations:
            label = f"[{citation['number']}] {citation['label']}"
            if citation.get("doc_name") == DATABASE:
                st.markdown(plain(label))
                if response.get("sql"):
                    st.code(response["sql"], language="sql")
            elif st.toggle(label, key=f"source-{id(response)}-{citation['number']}"):
                found = page(citation["doc_name"], int(citation["page"]))
                st.text(found["text"] if found else "The page couldn't be loaded.")


def show_steps(events: list[dict[str, Any]]) -> None:
    timed = [e for e in events if e["kind"] == "end"]
    if not timed:
        return
    with st.expander("Steps"):
        rows = [{"step": STEPS.get(e["node"], e["node"]), "ms": e.get("ms")} for e in timed]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        route = next((e for e in events if e.get("event") == "route"), None)
        if route:
            st.caption(f"Route: {route.get('route')} ({route.get('router')}, {route.get('model')})")


def results_page() -> None:
    st.title("Evaluation results")
    st.caption(
        "Headline numbers with 95% intervals: bootstrap, or exact binomial when a share sits at "
        "0 or 1. Each comes from a run in eval/results; the reports in docs/eval explain them."
    )
    rows = []
    for area, what, folder, metric in HEADLINES:
        path = RESULTS / folder / "summary.json"
        if not path.is_file():
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        value = summary["metrics"][metric]
        low, high = interval(value, int(summary["questions"]))
        rows.append(
            {
                "Area": area,
                "What": what,
                "Questions": summary["questions"],
                "Score": round(value["mean"], 3),
                "95% interval": f"{low:.3f} to {high:.3f}",
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("No results found under eval/results.")


def interval(value: dict[str, Any], n: int) -> tuple[float, float]:
    """The run's bootstrap interval, or the exact binomial one when the bootstrap touches 0
    or 1 on a share of right answers, as the reports give it (ADR-0007)."""
    low, high = float(value["low"]), float(value["high"])
    right = float(value["mean"]) * n
    if n > 0 and (high >= 1.0 or low <= 0.0) and abs(right - round(right)) < 1e-6:
        return exact_interval(round(right), n)
    return low, high


def main() -> None:
    st.set_page_config(
        page_title="Filings Research Copilot", page_icon=":material/plagiarism:", layout="wide"
    )
    navigation = st.navigation(
        [
            st.Page(ask_page, title="Ask", icon=":material/chat:", default=True),
            st.Page(
                results_page, title="Results", icon=":material/monitoring:", url_path="results"
            ),
        ]
    )
    navigation.run()


main()
