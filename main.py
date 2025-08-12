from agents.agent1_req_refiner import refine_requirement
from agents.agent2_code_gen import generate_mr_description
from agents.workflows import create_modernize_graph
from git_handler import AgenticGitHandler
from datetime import datetime
import yaml
import os
import git
from langchain_google_genai import ChatGoogleGenerativeAI

with open("integration.yml") as f:
    config = yaml.safe_load(f)

def generate_mr_description(plan: str, user_req: str) -> str:
    llm = ChatGoogleGenerativeAI(model=config["gemini"]["model"], google_api_key=config["gemini"]["api_key"])
    prompt = (
        "Given the following modernization plan and user requirement, generate a concise, clear merge request description. "
        "Summarize the plan and briefly describe the main implementation changes. "
        "Use markdown for readability if appropriate.\n\n"
        f"User Requirement:\n{user_req}\n\n"
        f"Modernization Plan:\n{plan}\n"
    )
    result = llm.invoke(prompt).content
    if not isinstance(result, str):
        result = str(result)
    return result

if __name__ == "__main__":
    user_req = input("Enter your requirement:\n")
    refined_req = refine_requirement(user_req)
    mr_description = generate_mr_description(refined_req, user_req)

    git_handler = AgenticGitHandler(
        gitlab_url=config["gitlab"]["url"],
        repo_path=config["gitlab"]["repo_path"],
        private_token=config["gitlab"]["private_token"],
        default_branch=config["gitlab"]["default_branch"],
        local_repo_dir=config["repository"]["local_dir"]
    )

    repo = git_handler.clone_or_pull_repo()
    branch_name = f"feature_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    commit_msg = "Modernized code via structured AI agent (LangGraph)"

    print("🔄 Starting LangGraph modernization process...")
    
    # Run the LangGraph workflow
    graph = create_modernize_graph()
    state = graph.invoke({"raw_requirement": user_req})
    
    if state.get('build_success'):
        # Delete all .bak files before committing
        for root, dirs, files in os.walk(config["repository"]["local_dir"]):
            for file in files:
                if file.endswith('.bak'):
                    bak_path = os.path.join(root, file)
                    try:
                        os.remove(bak_path)
                        print(f"Deleted backup file: {bak_path}")
                    except Exception as e:
                        print(f"Failed to delete backup file {bak_path}: {e}")
        
        # Remove any .bak files from git index if they are staged
        repo = git.Repo(config["repository"]["local_dir"])
        for root, dirs, files in os.walk(config["repository"]["local_dir"]):
            for file in files:
                if file.endswith('.bak'):
                    bak_path = os.path.relpath(os.path.join(root, file), config["repository"]["local_dir"]).replace(os.sep, '/')
                    try:
                        tracked_files = repo.git.ls_files(bak_path)
                        if tracked_files:
                            repo.git.rm("--cached", bak_path)
                    except Exception:
                        pass
        
        # Create merge request
        print("📤 Committing changes and creating merge request...")
        git_handler.apply_and_commit_changes(repo, branch_name, commit_msg)
        mr_url = git_handler.create_merge_request(
            branch_name, 
            config["gitlab"]["default_branch"], 
            user_req,
            mr_description
        )
        print("🎉 Merge Request created successfully!")
        print("Merge Request URL:", mr_url)
        
        # Print additional information
        if state.get('test_success'):
            print(f"✅ Test generation completed: {len(state.get('test_files', []))} test files created")
            print(f"📊 Coverage report: {state.get('coverage_report', 'No coverage data')}")
        
        if state.get('endpoint_health'):
            print(f"🚀 Application deployed successfully!")
            print(f"🌐 Endpoint URL: {state.get('endpoint_url')}")
            print(f"🏥 Health check: {state.get('actuator_health_url')}")
        
        print("✅ LangGraph modernization process completed!")
    else:
        print("❌ Build verification failed! Merge request not created.")
        print("Build Output:")
        print(state.get('build_output', 'No build output available'))
