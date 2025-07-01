from agent1_req_refiner import refine_requirement
from agent2_code_gen import generate_code
from agent3_test_gen import fix_and_build
from git_handler import AgenticGitHandler
from datetime import datetime
import yaml
import os

def apply_structured_changes(file_instructions, repo_dir):
    for file in file_instructions:
        path = os.path.join(repo_dir, file["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if file["action"] == "delete":
            if os.path.exists(path):
                os.remove(path)
                print(f"Deleted: {path}")
        elif file["action"] in ("update", "create"):
            with open(path, "w", encoding="utf-8") as f:
                f.write(file["content"])
            print(f"Written: {path}")

if __name__ == "__main__":
    user_req = input("Enter your requirement:\n")
    refined_req = refine_requirement(user_req)

    with open("integration.yml") as f:
        config = yaml.safe_load(f)

    git_handler = AgenticGitHandler(
        gitlab_url=config["gitlab"]["url"],
        repo_path=config["gitlab"]["repo_path"],
        private_token=config["gitlab"]["private_token"],
        default_branch=config["gitlab"]["default_branch"],
        local_repo_dir=config["repository"]["local_dir"]
    )

    repo = git_handler.clone_or_pull_repo()
    branch_name = f"feature_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    commit_msg = "Modernized code via structured AI agent"

    print("🔄 Starting code generation process...")
    
    # Step 1: Generate code changes
    print("📝 Generating code changes...")
    file_instructions = generate_code(refined_req)
    apply_structured_changes(file_instructions, config["repository"]["local_dir"])

    print("✅ Code generation completed!")
    
    # Step 2: Run Agent 3's fix_and_build (mvn clean compile + LLM fix loop)
    def create_mr_callback():
        print("📤 Committing changes and creating merge request...")
        git_handler.apply_and_commit_changes(repo, branch_name, commit_msg)
        mr_url = git_handler.create_merge_request(
            branch_name, 
            config["gitlab"]["default_branch"], 
            "Modernized Code", 
            "Updated code using agentic AI with comprehensive modernization"
        )
        print("🎉 Merge Request created successfully!")
        print("Merge Request URL:", mr_url)

    print("🔍 Running build verification and auto-fix with Agent 3...")
    build_success, build_output = fix_and_build(config["repository"]["local_dir"], max_attempts=3, on_success=create_mr_callback)
    
    if not build_success:
        print("❌ Build verification failed! Merge request not created.")
        print("Build Output:")
        print(build_output)
    else:
        print("✅ Build and merge request process completed!")
