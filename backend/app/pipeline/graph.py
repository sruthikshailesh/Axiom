"""One LangGraph graph: researcher -> extractor -> verifier."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.pipeline.extractor import extractor_node
from app.pipeline.researcher import researcher_node
from app.pipeline.run_state import mark_status
from app.pipeline.verifier import verifier_node


class PipelineState(TypedDict, total=False):
    run_id: int
    question: str
    chunks: List[Dict[str, Any]]
    claims: List[int]
    verification: Dict[str, Any]
    log: List[str]
    failed: bool


def build_graph(db: Session):
    # Each node publishes its stage so a polling client can show progress.
    def researcher(state: PipelineState) -> Dict[str, Any]:
        mark_status(db, state["run_id"], "researching")
        return researcher_node(state, db)

    def extractor(state: PipelineState) -> Dict[str, Any]:
        mark_status(db, state["run_id"], "extracting")
        return extractor_node(state, db)

    def verifier(state: PipelineState) -> Dict[str, Any]:
        mark_status(db, state["run_id"], "verifying")
        return verifier_node(state, db)

    def after_researcher(state: PipelineState) -> str:
        return "stop" if state.get("failed") else "continue"

    graph = StateGraph(PipelineState)
    graph.add_node("researcher", researcher)
    graph.add_node("extractor", extractor)
    graph.add_node("verifier", verifier)

    graph.set_entry_point("researcher")
    graph.add_conditional_edges(
        "researcher", after_researcher, {"continue": "extractor", "stop": END}
    )
    graph.add_edge("extractor", "verifier")
    graph.add_edge("verifier", END)

    return graph.compile()


def run_pipeline(db: Session, run_id: int, question: str) -> Dict[str, Any]:
    """Run the graph synchronously for one already-created run."""
    initial: PipelineState = {
        "run_id": run_id,
        "question": question,
        "chunks": [],
        "claims": [],
        "log": [],
        "failed": False,
    }
    return build_graph(db).invoke(initial)
