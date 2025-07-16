from flask import Flask, request, jsonify
from agents.agent1_req_refiner import refine_requirement
from agents.agent2_code_gen import generate_code
from agents.agent3_test_gen import fix_and_build
from git_handler import AgenticGitHandler
from datetime import datetime
import yaml
import os
import git
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def generate_mr_description(plan: str, user_req: str) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI
    # Get the directory where this script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "integration.yml")

    with open(config_path) as f:
        config = yaml.safe_load(f)

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


@app.route('/requirement', methods=['POST'])
def modernize_project():
    try:
        # Get request data
        data = request.get_json()
        user_req = data.get('requestMessage')
        repo_path = data.get('githubRepo')  # This will now be just the repo path

        if not user_req or not repo_path:
            return jsonify({
                'error': 'Missing required fields: requirement and gitlab_repo_url (repo path)'
            }), 400

        # Validate repo path format (should be username/repo-name)
        if '/' not in repo_path or repo_path.count('/') != 1:
            return jsonify({
                'error': 'Invalid repo path format. Must be in format: username/repo-name'
            }), 400

        # Load configuration
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "integration.yml")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Update config to use the provided repo path
        config["gitlab"]["repo_path"] = repo_path

        # Use the same approach as main.py
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

        max_regeneration_attempts = 3
        for regeneration_attempt in range(max_regeneration_attempts):
            print(f"🔄 Regeneration attempt {regeneration_attempt + 1}/{max_regeneration_attempts}")

            # Step 1: Generate code changes
            print("📝 Generating code changes...")
            file_instructions = generate_code(user_req)
            apply_structured_changes(file_instructions, config["repository"]["local_dir"])

            print("✅ Code generation completed!")

            # Step 2: Run Agent 3's fix_and_build
            print("🔍 Running build verification and auto-fix with Agent 3...")
            build_success, build_output = fix_and_build(config["repository"]["local_dir"], max_attempts=5,
                                                        on_success=None)

            if build_success:
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
                            bak_path = os.path.relpath(os.path.join(root, file),
                                                       config["repository"]["local_dir"]).replace(os.sep, '/')
                            try:
                                tracked_files = repo.git.ls_files(bak_path)
                                if tracked_files:
                                    repo.git.rm("--cached", bak_path)
                            except Exception:
                                pass

                # Generate MR description
                refined_req = refine_requirement(user_req)
                mr_description = generate_mr_description(refined_req, user_req)

                # Create the merge request and get the URL
                print("📤 Committing changes and creating merge request...")
                git_handler.apply_and_commit_changes(repo, branch_name, commit_msg)
                mr_url = git_handler.create_merge_request(
                    branch_name,
                    config["gitlab"]["default_branch"],
                    user_req,
                    mr_description
                )

                return jsonify({
                    'success': True,
                    'mr_details': mr_description,
                    'mr_link': mr_url,
                    'branch_name': branch_name,
                    'regeneration_attempts': regeneration_attempt + 1
                })
            else:
                print(f"❌ Build failed after 5 attempts in regeneration {regeneration_attempt + 1}")
                if regeneration_attempt < max_regeneration_attempts - 1:
                    print("🔄 Calling Agent 2 to regenerate code...")
                    continue

        # If we get here, all regeneration attempts failed
        return jsonify({
            'success': False,
            'error': 'Build verification failed after all regeneration attempts',
            'build_output': build_output,
            'regeneration_attempts': max_regeneration_attempts
        }), 500

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {error_details}")

        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500


@app.route('/summarize', methods=['POST'])
def summarize_project():
    try:
        data = request.get_json()
        repo_path = data.get('githubRepo')
        if not repo_path:
            return jsonify({'error': 'Missing required field: githubRepo'}), 400
        if '/' not in repo_path or repo_path.count('/') != 1:
            return jsonify({'error': 'Invalid repo path format. Must be in format: username/repo-name'}), 400

        # Load configuration
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "integration.yml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["gitlab"]["repo_path"] = repo_path

        # Clone or pull repo
        git_handler = AgenticGitHandler(
            gitlab_url=config["gitlab"]["url"],
            repo_path=config["gitlab"]["repo_path"],
            private_token=config["gitlab"]["private_token"],
            default_branch=config["gitlab"]["default_branch"],
            local_repo_dir=config["repository"]["local_dir"]
        )
        git_handler.clone_or_pull_repo()
        repo_dir = config["repository"]["local_dir"]

        # Read all code files (skip binary/large files)
        def get_code_files(base_dir):
            code_files = []
            for root, _, files in os.walk(base_dir):
                for file in files:
                    if file.endswith((".py", ".java", ".js", ".ts", ".xml", ".yml", ".yaml", ".properties", ".md")):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                rel_path = os.path.relpath(file_path, base_dir)
                                # Limit individual file size to 30KB
                                if len(content) < 30_000:
                                    code_files.append(f"// FILE: {rel_path}\n{content}")
                        except Exception:
                            continue
            return code_files

        code_files = get_code_files(repo_dir)
        code_snapshot = "\n\n".join(code_files)
        if not code_snapshot:
            return jsonify({'error': 'No code files found in the repository.'}), 404

        # Summarize with Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(model=config["gemini"]["model"], google_api_key=config["gemini"]["api_key"])
        prompt = (
            "You are an expert software analyst. Given the following codebase, provide a simple, point-wise summary of the project. "
            "Use clear, non-technical language suitable for a non-developer. List the main features, technologies, and structure. "
            "If possible, mention the main purpose of the project, key components, and any notable patterns.\n\n"
            "Codebase Snapshot:\n" + code_snapshot + "\n\n"
            "Summary (in bullet points):"
        )
        result = llm.invoke(prompt).content
        if not isinstance(result, str):
            result = str(result)
        return jsonify({'summary': result})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {error_details}")
        return jsonify({'error': f'An error occurred: {str(e)}', 'details': error_details}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Agentic AI API is running'
    })


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
