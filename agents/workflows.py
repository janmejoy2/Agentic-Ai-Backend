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
    build_attempts: int  # Track number of build attempts
    max_build_attempts: int  # Maximum allowed build attempts
    recode_triggered: bool  # Flag to indicate if recoding was triggered
    recode_attempts: int  # Track number of recode attempts


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
    """Agent 4: Build and deploy the application with retry mechanism"""
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
    
    # Initialize retry tracking if not present
    build_attempts = state.get("build_attempts", 0)
    max_build_attempts = config.get("retry", {}).get("max_build_attempts", 3)
    recode_triggered = state.get("recode_triggered", False)
    recode_attempts = state.get("recode_attempts", 0)
    max_recode_attempts = config.get("retry", {}).get("max_recode_attempts", 2)
    enable_auto_recode = config.get("retry", {}).get("enable_auto_recode", True)
    
    print(f"🚀 Agent 4: Starting build and deployment (attempt {build_attempts + 1}/{max_build_attempts})...")
    
    # Agent 4 is completely independent - no need to check Agent 3 status
    # It will build and deploy regardless of whether tests were generated or skipped
    print("🚀 Agent 4: Building and deploying independently of test generation status...")
    
    success, message, build_info = create_build_deploy_agent_workflow(repo_dir)
    
    # Update build attempts counter
    build_attempts += 1
    
    if success:
        print("✅ Build successful!")
        return {
            "build_success": True,
            "build_output": build_info.get("build_output", ""),
            "endpoint_url": build_info.get("endpoint_url"),
            "endpoint_health": build_info.get("endpoint_health"),
            "actuator_health_url": build_info.get("actuator_health_url"),
            "build_attempts": build_attempts
        }
    else:
        print(f"❌ Build failed on attempt {build_attempts}")
        
        # Check if we should trigger recoding
        if (build_attempts >= max_build_attempts and 
            not recode_triggered and 
            enable_auto_recode and 
            recode_attempts < max_recode_attempts):
            print(f"🔄 Maximum build attempts ({max_build_attempts}) reached. Triggering recoding with Agent 2...")
            return {
                "build_success": False,
                "build_output": build_info.get("build_output", ""),
                "endpoint_url": None,
                "endpoint_health": None,
                "actuator_health_url": None,
                "build_attempts": build_attempts,
                "recode_triggered": True,
                "recode_attempts": recode_attempts + 1
            }
        elif recode_attempts >= max_recode_attempts:
            print(f"❌ Maximum recode attempts ({max_recode_attempts}) reached. Giving up.")
            return {
                "build_success": False,
                "build_output": build_info.get("build_output", "") + "\n\nMaximum recode attempts reached. Build failed permanently.",
                "endpoint_url": None,
                "endpoint_health": None,
                "actuator_health_url": None,
                "build_attempts": build_attempts
            }
        else:
            # Continue with normal build failure
            return {
                "build_success": False,
                "build_output": build_info.get("build_output", ""),
                "endpoint_url": None,
                "endpoint_health": None,
                "actuator_health_url": None,
                "build_attempts": build_attempts
            }


def node_recode_and_retry(state: ModernizeState) -> ModernizeState:
    """Trigger recoding with Agent 2 and reset build attempts"""
    config = _load_config()
    recode_attempts = state.get("recode_attempts", 0)
    max_recode_attempts = config.get("retry", {}).get("max_recode_attempts", 2)
    
    print(f"🔄 Agent 2: Triggering recoding due to build failures (recode attempt {recode_attempts}/{max_recode_attempts})...")
    
    try:
        # Call Agent 2 for recoding
        files = generate_code(state["refined_requirement"])
        
        # Apply the new code
        repo_dir = config["repository"]["local_dir"]
        from utils.file_ops import apply_structured_changes, ensure_clean_modernization
        apply_structured_changes(files, repo_dir)
        ensure_clean_modernization(repo_dir)
        
        print("✅ Recoding completed successfully. Resetting build attempts for retry...")
        
        return {
            "file_instructions": files,
            "build_attempts": 0,  # Reset build attempts
            "recode_triggered": False  # Reset recode flag
        }
    except Exception as e:
        print(f"❌ Recoding failed: {e}")
        return {
            "build_success": False,
            "build_output": f"Recoding failed: {str(e)}",
            "endpoint_url": None,
            "endpoint_health": None,
            "actuator_health_url": None,
            "recode_triggered": False  # Reset recode flag to prevent infinite loop
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
    graph.add_node("recode_and_retry", node_recode_and_retry)

    graph.add_edge(START, "refine")
    graph.add_edge("refine", "codegen")
    graph.add_edge("codegen", "test_gen")
    graph.add_edge("test_gen", "build_deploy")
    
    # Add conditional edge for recoding
    def should_recode(state: ModernizeState) -> str:
        if state.get("recode_triggered", False):
            return "recode_and_retry"
        elif state.get("build_success", False):
            return END
        else:
            # Check if we've reached maximum recode attempts
            config = _load_config()
            max_recode_attempts = config.get("retry", {}).get("max_recode_attempts", 2)
            recode_attempts = state.get("recode_attempts", 0)
            
            if recode_attempts >= max_recode_attempts:
                print(f"❌ Maximum recode attempts ({max_recode_attempts}) reached. Ending workflow.")
                return END
            else:
                return "build_deploy"  # Retry build
    
    graph.add_conditional_edges("build_deploy", should_recode)
    graph.add_edge("recode_and_retry", "build_deploy")  # After recoding, try build again

    return graph.compile()

