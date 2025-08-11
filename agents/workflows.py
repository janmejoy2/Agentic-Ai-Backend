from __future__ import annotations

from typing import TypedDict, Optional, List, Dict, Any

from langgraph.graph import StateGraph, START, END

from .agent1_req_refiner import refine_requirement
from .agent2_code_gen import generate_code
from .agent3_test_gen import create_test_agent_workflow
from .agent4_build_deploy import create_build_deploy_agent_workflow


class ModernizeState(TypedDict, total=False):
    raw_requirement: str
    refined_requirement: str
    file_instructions: List[Dict[str, Any]]
    test_files: List[Dict[str, Any]]
    coverage_data: Dict[str, Any]
    coverage_report: str
    test_success: bool
    tests_skipped: bool  # Flag to indicate if tests were skipped
    build_success: bool
    build_output: str
    endpoint_url: Optional[str]
    endpoint_health: Optional[bool]
    actuator_health_url: Optional[str]


def node_refine(state: ModernizeState) -> ModernizeState:
    refined = refine_requirement(state["raw_requirement"])
    return {"refined_requirement": refined}


def node_codegen(state: ModernizeState) -> ModernizeState:
    files = generate_code(state["refined_requirement"])  # list of {path, action, content?}
    # Apply files to repo
    config = _load_config()
    repo_dir = config["repository"]["local_dir"]
    from utils.file_ops import apply_structured_changes, ensure_clean_modernization
    apply_structured_changes(files, repo_dir)
    
    # Perform additional cleanup to remove any legacy files that might have been missed
    ensure_clean_modernization(repo_dir)
    
    return {"file_instructions": files}


def node_test_gen(state: ModernizeState) -> ModernizeState:
    """Agent 3: Generate comprehensive tests and check coverage"""
    config = _load_config()
    
    # Check if test generation should be skipped
    if config.get("agents", {}).get("skip_test_generation", False):
        print("⏭️ Skipping Agent 3 (test generation) - disabled in configuration")
        return {
            "test_success": True,  # Mark as successful since we're skipping
            "test_files": [],
            "coverage_data": {},
            "coverage_report": "Test generation skipped (disabled in configuration)",
            "tests_skipped": True  # Flag to indicate tests were skipped
        }
    
    repo_dir = config["repository"]["local_dir"]
    success, message, test_info = create_test_agent_workflow(repo_dir)
    
    return {
        "test_success": success,
        "test_files": test_info.get("test_files", []),
        "coverage_data": test_info.get("coverage_data", {}),
        "coverage_report": test_info.get("coverage_report", "No coverage data"),
        "tests_skipped": False  # Flag to indicate tests were not skipped
    }


def node_build_deploy(state: ModernizeState) -> ModernizeState:
    """Agent 4: Build and deploy the application - completely independent of Agent 3"""
    config = _load_config()
    
    # Check if build and deploy should be skipped
    if config.get("agents", {}).get("skip_build_deploy", False):
        print("⏭️ Skipping Agent 4 (build & deploy) - disabled in configuration")
        return {
            "build_success": True,  # Mark as successful since we're skipping
            "build_output": "Build and deploy skipped (disabled in configuration)",
            "endpoint_url": None,
            "endpoint_health": None,
            "actuator_health_url": None
        }
    
    repo_dir = config["repository"]["local_dir"]
    
    # Agent 4 is completely independent - no need to check Agent 3 status
    # It will build and deploy regardless of whether tests were generated or skipped
    print("🚀 Agent 4: Building and deploying independently of test generation status...")
    
    success, message, build_info = create_build_deploy_agent_workflow(repo_dir)
    
    return {
        "build_success": success,
        "build_output": build_info.get("build_output", ""),
        "endpoint_url": build_info.get("endpoint_url"),
        "endpoint_health": build_info.get("endpoint_health"),
        "actuator_health_url": build_info.get("actuator_health_url")
    }



def _load_config() -> Dict[str, Any]:
    import os
    import yaml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_modernize_graph():
    graph = StateGraph(ModernizeState)
    graph.add_node("refine", node_refine)
    graph.add_node("codegen", node_codegen)
    graph.add_node("test_gen", node_test_gen)
    graph.add_node("build_deploy", node_build_deploy)

    graph.add_edge(START, "refine")
    graph.add_edge("refine", "codegen")
    graph.add_edge("codegen", "test_gen")
    graph.add_edge("test_gen", "build_deploy")
    graph.add_edge("build_deploy", END)

    return graph.compile()

