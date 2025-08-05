from flask import Flask, request, jsonify, send_from_directory
from agents.agent1_req_refiner import refine_requirement
from agents.agent2_code_gen import generate_code, generate_mr_description
from agents.agent3_test_gen import fix_and_build, build_and_deploy
from git_handler import AgenticGitHandler
from datetime import datetime
import yaml
import os
import git
import shutil
from flask_cors import CORS
import uuid
from plantuml import PlantUML
from plantuml import PlantUMLHTTPError

app = Flask(__name__)
CORS(app)


# Applies file changes (create, update, delete) as instructed by the LLM/code generator to the local repo directory.
def apply_structured_changes(file_instructions, repo_dir):
    for file in file_instructions:
        path = os.path.join(repo_dir, file["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if file["action"] == "delete":
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"Deleted directory: {path}")
                else:
                    os.remove(path)
                    print(f"Deleted file: {path}")
        elif file["action"] in ("update", "create"):
            with open(path, "w", encoding="utf-8") as f:
                f.write(file["content"])
            print(f"Written: {path}")


def render_plantuml_to_png(plantuml_code, output_dir="diagrams"):
    os.makedirs(output_dir, exist_ok=True)
    unique_id = str(uuid.uuid4())
    png_path = os.path.join(output_dir, f"diagram_{unique_id}.png")
    # Ensure PlantUML code has @startuml/@enduml
    code = plantuml_code.strip()
    if not code.startswith("@startuml"):
        code = "@startuml\n" + code
    if not code.endswith("@enduml"):
        code = code + "\n@enduml"
    # Write to a temp .puml file
    puml_path = os.path.join(output_dir, f"diagram_{unique_id}.puml")
    with open(puml_path, "w", encoding="utf-8") as f:
        f.write(code)
    # Render using PlantUML server (default public server)
    server = PlantUML(url="http://www.plantuml.com/plantuml/img/")
    try:
        server.processes_file(puml_path, png_path)
    except PlantUMLHTTPError as e:
        print(f"PlantUMLHTTPError occurred: {e}")
        return None
    return png_path


# Validates the incoming request data for the modernize_project endpoint. Returns (error_response, user_req, repo_path) tuple.
def validate_modernize_request(data):
    user_req = data.get('requestMessage')
    repo_path = data.get('githubRepo')
    flow_create = data.get('flowchart')
    if not user_req or not repo_path:
        return ({
                    'error': 'Missing required fields: requirement and gitlab_repo_url (repo path)'
                }, None, None)
    if '/' not in repo_path or repo_path.count('/') != 1:
        return ({
                    'error': 'Invalid repo path format. Must be in format: username/repo-name'
                }, None, None)
    return (None, user_req, repo_path, flow_create)


# Loads integration.yml config and updates the gitlab repo_path. Returns the config dict.
def load_and_update_config(repo_path):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "integration.yml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    config["gitlab"]["repo_path"] = repo_path
    return config


# Clones or pulls the repository as specified in the config. Returns the AgenticGitHandler instance and repo object.
def clone_or_pull_repo(config):
    git_handler = AgenticGitHandler(
        gitlab_url=config["gitlab"]["url"],
        repo_path=config["gitlab"]["repo_path"],
        private_token=config["gitlab"]["private_token"],
        default_branch=config["gitlab"]["default_branch"],
        local_repo_dir=config["repository"]["local_dir"]
    )
    repo = git_handler.clone_or_pull_repo()
    return git_handler, repo


# Generates code changes using the LLM and applies them to the repo directory.
def generate_and_apply_code(user_req, config):
    file_instructions = generate_code(user_req)
    apply_structured_changes(file_instructions, config["repository"]["local_dir"])
    return file_instructions


# Runs build and deploy, cleans up .bak files, and returns build results.
def build_and_cleanup(config, max_attempts=3):
    build_success, build_output, endpoint_url, health_ok, health_url = build_and_deploy(
        config["repository"]["local_dir"], max_attempts=max_attempts)
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
                    bak_path = os.path.relpath(os.path.join(root, file), config["repository"]["local_dir"]).replace(
                        os.sep, '/')
                    try:
                        repo.index.remove([bak_path], working_tree=True)
                    except Exception:
                        pass
    return build_success, build_output, endpoint_url, health_ok, health_url


# Handles the regeneration loop: generates code, builds, and returns result or error after max attempts.
def regenerate_until_success(user_req, config, max_regeneration_attempts, git_handler, branch_name, commit_msg):
    for regeneration_attempt in range(max_regeneration_attempts):
        print(f"🔄 Regeneration attempt {regeneration_attempt + 1}/{max_regeneration_attempts}")
        # Step 1: Generate code changes
        print("📝 Generating code changes...")
        file_instructions = generate_and_apply_code(user_req, config)
        print("✅ Code generation completed!")
        # Step 2: Run Agent 3's fix_and_build and cleanup
        print("🔍 Running build verification and auto-fix with Agent 3...")
        build_success, build_output, endpoint_url, health_ok, health_url = build_and_cleanup(config, max_attempts=3)
        if build_success:
            return {
                'success': True,
                'file_instructions': file_instructions,
                'regeneration_attempts': regeneration_attempt + 1,
                'endpoint_url': endpoint_url,
                'endpoint_health': health_ok,
                'actuator_health_url': health_url,
                'build_output': build_output
            }
        else:
            print(f"❌ Build failed after 3 attempts in regeneration {regeneration_attempt + 1}")
            if regeneration_attempt < max_regeneration_attempts - 1:
                print("🔄 Calling Agent 2 to regenerate code...")
    # If we get here, all regeneration attempts failed
    return {
        'success': False,
        'error': 'Build verification failed after all regeneration attempts',
        'build_output': build_output,
        'regeneration_attempts': max_regeneration_attempts
    }


# Flask route: Modernizes a project by cloning a repo, generating code changes with LLM, building, and returning results.
@app.route('/requirement', methods=['POST'])
def modernize_project():
    try:
        # Get request data
        data = request.get_json()
        error_response, user_req, repo_path, flow_create = validate_modernize_request(data)
        if error_response:
            return jsonify(error_response), 400

        config = load_and_update_config(repo_path)

        git_handler, repo = clone_or_pull_repo(config)
        branch_name = f"feature_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        commit_msg = "Modernized code via structured AI agent"

        print("🔄 Starting code generation process...")

        max_regeneration_attempts = 3
        regen_result = regenerate_until_success(user_req, config, max_regeneration_attempts, git_handler, branch_name,
                                                commit_msg)
        if regen_result['success']:
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
            # Generate PlantUML diagram for the modernized codebase
            code_files = get_code_files_for_summary(config["repository"]["local_dir"])
            code_snapshot = "\n\n".join(code_files)
            if flow_create:
               plantuml_result = generate_plantuml_diagram(code_snapshot, config)
               png_path = render_plantuml_to_png(plantuml_result)
            else:
                png_path = None
            return jsonify({
                'success': True,
                'mr_details': mr_description,
                'mr_link': mr_url,
                'branch_name': branch_name,
                'regeneration_attempts': regen_result['regeneration_attempts'],
                'endpoint_url': regen_result['endpoint_url'] if regen_result['endpoint_health'] else None,
                'endpoint_health': regen_result['endpoint_health'],
                'actuator_health_url': regen_result['actuator_health_url'] if regen_result['endpoint_health'] else None,
                'plantuml_png': png_path
            })
        else:
            return jsonify({
                'success': False,
                'error': regen_result['error'],
                'build_output': regen_result['build_output'],
                'regeneration_attempts': regen_result['regeneration_attempts']
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


# Collects all relevant code files from the given base directory for summarization, skipping large/binary files.
def get_code_files_for_summary(base_dir):
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


# Uses Gemini LLM to generate a non-technical, bullet-point summary of the codebase from the code snapshot.
def generate_gemini_summary(code_snapshot, config):
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
    return result


# Uses Gemini LLM to generate a PlantUML diagram (as text) representing the high-level structure of the codebase.
def generate_plantuml_diagram(code_snapshot, config):
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model=config["gemini"]["model"], google_api_key=config["gemini"]["api_key"])
    plantuml_prompt = (
            "You are an expert software architect. Given the following codebase, generate a PlantUML diagram (using @startuml ... @enduml) that represents the high-level structure of the entire codebase. "
            "Show the main modules, classes, and their relationships (such as dependencies, inheritance, or usage). "
            "Focus on the most important components and their connections. Do not include code, only the diagram.\n\n"
            "IMPORTANT: Only include the main application flow. Ignore and exclude any test classes, test files, or test-related code from the diagram.\n"
            "Make the diagram clean and easy to read, with a simple, linear flow (top-down or left-to-right). Minimize crossing lines and clutter. Use PlantUML layout directives if needed.\n\n"
            "Codebase Snapshot:\n" + code_snapshot + "\n\n"
                                                     "PlantUML diagram:"
    )
    plantuml_result = llm.invoke(plantuml_prompt).content
    if not isinstance(plantuml_result, str):
        plantuml_result = str(plantuml_result)
    # Clean up markdown formatting if present
    if plantuml_result.strip().startswith("```plantuml"):
        plantuml_result = plantuml_result.strip().lstrip("```plantuml").rstrip("```").strip()
    elif plantuml_result.strip().startswith("```"):
        plantuml_result = plantuml_result.strip().lstrip("```").rstrip("```").strip()
    return plantuml_result


@app.route('/summarize', methods=['POST'])
def summarize_project():
    try:
        data = request.get_json()
        repo_path = data.get('githubRepo')
        generate_flow = data.get('flowchart')
        if not repo_path:
            return jsonify({'error': 'Missing required field: githubRepo'}), 400
        if '/' not in repo_path or repo_path.count('/') != 1:
            return jsonify({'error': 'Invalid repo path format. Must be in format: username/repo-name'}), 400

        config = load_and_update_config(repo_path)
        git_handler, _ = clone_or_pull_repo(config)
        repo_dir = config["repository"]["local_dir"]

        code_files = get_code_files_for_summary(repo_dir)
        code_snapshot = "\n\n".join(code_files)
        if not code_snapshot:
            return jsonify({'error': 'No code files found in the repository.'}), 404

        result = generate_gemini_summary(code_snapshot, config)
        if generate_flow:
            plantuml_result = generate_plantuml_diagram(code_snapshot, config)
            png_path = render_plantuml_to_png(plantuml_result)
            if png_path is None:
                return jsonify({'summary': result, 'plantuml_png': None,
                                'error': 'Failed to generate PlantUML diagram image.'}), 200
            return jsonify({'summary': result, 'plantuml_png': png_path})
        else:
            return jsonify({'summary': result, 'plantuml_png': None})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {error_details}")
        return jsonify({'error': f'An error occurred: {str(e)}', 'details': error_details}), 500


@app.route('/diagrams/<filename>')
def serve_diagram(filename):
    """Serve diagram files from the diagrams directory"""
    diagrams_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagrams')
    return send_from_directory(diagrams_dir, filename)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Agentic AI API is running'
    })


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
