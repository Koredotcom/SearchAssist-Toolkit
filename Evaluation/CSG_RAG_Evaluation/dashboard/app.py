from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "eval.db"


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_runs() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM eval_run ORDER BY started_at DESC", conn
    )
    return df


def load_results(run_id: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT er.*, tc.question, tc.expected_answer, tc.question_type,
               tc.difficulty, tc.expected_behavior, tc.human_validated
        FROM eval_result er
        JOIN test_case tc ON tc.tc_id = er.tc_id
        WHERE er.run_id = ?
        """,
        conn,
        params=(run_id,),
    )
    if not df.empty:
        df["scores"] = df["scores"].apply(lambda x: json.loads(x) if x else {})
        df["faithfulness"] = df["scores"].apply(lambda s: s.get("faithfulness"))
        df["relevance"] = df["scores"].apply(lambda s: s.get("relevance"))
        df["completeness"] = df["scores"].apply(lambda s: s.get("completeness"))
        df["doc_retrieved"] = df["scores"].apply(lambda s: s.get("doc_retrieved", False))
    return df


st.set_page_config(page_title="RAG Evaluator", layout="wide")
st.title("RAG Evaluation Dashboard")

runs_df = load_runs()

if runs_df.empty:
    st.info("No evaluation runs yet. Run `python main.py evaluate --version 1.0.0` to start.")
    st.stop()

# ── Headline metrics ──────────────────────────────────────────────────────────
st.subheader("Runs")
latest = runs_df.iloc[0]
col1, col2, col3, col4 = st.columns(4)
total = latest["total_cases"] or 1
passed = latest["passed_cases"] or 0
col1.metric("Latest Pass Rate", f"{passed/total*100:.1f}%")
col2.metric("Total Cases", total)
col3.metric("Passed", passed)
col4.metric("Status", latest["status"].upper())

st.dataframe(
    runs_df[["run_id", "started_at", "rag_version", "golden_set_version", "status", "passed_cases", "total_cases"]],
    use_container_width=True,
)

# ── Run selector ──────────────────────────────────────────────────────────────
selected_run = st.selectbox("Select run to inspect", runs_df["run_id"].tolist())
results_df = load_results(selected_run)

if results_df.empty:
    st.info("No results for this run yet.")
    st.stop()

# ── Pass rate by question type ────────────────────────────────────────────────
st.subheader("Pass Rate by Question Type")
results_df["pass"] = (
    results_df["failure_category"].isin(["none"])
).astype(int)

by_type = (
    results_df.groupby("question_type")["pass"]
    .agg(["sum", "count"])
    .reset_index()
)
by_type["pass_rate"] = by_type["sum"] / by_type["count"] * 100
fig = px.bar(by_type, x="question_type", y="pass_rate", color="pass_rate",
             range_y=[0, 100], color_continuous_scale="RdYlGn",
             labels={"pass_rate": "Pass Rate %", "question_type": "Type"})
st.plotly_chart(fig, use_container_width=True)

# ── Score distributions ───────────────────────────────────────────────────────
st.subheader("Score Distributions")
score_cols = ["faithfulness", "relevance", "completeness"]
available = [c for c in score_cols if c in results_df.columns and results_df[c].notna().any()]
if available:
    fig2 = px.box(results_df.melt(value_vars=available, var_name="metric", value_name="score"),
                  x="metric", y="score", range_y=[0, 5])
    st.plotly_chart(fig2, use_container_width=True)

# ── Failure breakdown ─────────────────────────────────────────────────────────
st.subheader("Failure Categories")
fail_counts = results_df["failure_category"].value_counts().reset_index()
fail_counts.columns = ["category", "count"]
fig3 = px.pie(fail_counts, names="category", values="count")
st.plotly_chart(fig3, use_container_width=True)

# ── Drill-down table ──────────────────────────────────────────────────────────
st.subheader("Individual Results")
show_failures_only = st.checkbox("Show failures only", value=False)
display_df = results_df if not show_failures_only else results_df[results_df["failure_category"] != "none"]

st.dataframe(
    display_df[[
        "tc_id", "question_type", "difficulty", "question",
        "rag_response", "failure_category", "faithfulness", "relevance", "completeness",
    ]].rename(columns={"rag_response": "answer"}),
    use_container_width=True,
)

with st.expander("Full result detail"):
    if st.selectbox("Select test case", display_df["tc_id"].tolist(), key="tc_select"):
        tc_id = st.session_state["tc_select"]
        row = display_df[display_df["tc_id"] == tc_id].iloc[0]
        st.json({
            "question": row["question"],
            "expected_answer": row["expected_answer"],
            "rag_answer": row["rag_response"],
            "failure_category": row["failure_category"],
            "scores": row["scores"],
            "judge_rationale": row.get("judge_rationale", ""),
        })
