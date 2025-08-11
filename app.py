from flask import Flask, request, jsonify, send_from_directory
from agents.agent1_req_refiner import refine_requirement
from agents.agent2_code_gen import generate_code, generate_mr_description
from agents.agent3_test_gen import create_test_agent_workflow
from agents.agent4_build_deploy import create_build_deploy_agent_workflow
from agents.workflows import create_modernize_graph
from utils.file_ops import apply_structured_changes
from utils.cleanup import setup_cleanup_handlers, cleanup_directories
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

# Set up cleanup handlers for graceful shutdown
setup_cleanup_handlers()


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
    if not user_req or not repo_path:
        return ({
            'error': 'Missing required fields: requirement and gitlab_repo_url (repo path)'
        }, None, None)
    if '/' not in repo_path or repo_path.count('/') != 1:
        return ({
            'error': 'Invalid repo path format. Must be in format: username/repo-name'
        }, None, None)
    return (None, user_req, repo_path)


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
    
    # Perform additional cleanup to remove any legacy files that might have been missed
    from utils.file_ops import ensure_clean_modernization
    ensure_clean_modernization(config["repository"]["local_dir"])
    
    return file_instructions


# Flask route: Modernizes a project using LangGraph workflow
@app.route('/requirement', methods=['POST'])
def modernize_project():
    try:
        data = request.get_json()
        error_response, user_req, repo_path = validate_modernize_request(data)
        if error_response:
            return jsonify(error_response), 400

        config = load_and_update_config(repo_path)
        git_handler, repo = clone_or_pull_repo(config)

        branch_name = f"feature_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        commit_msg = "Modernized code via structured AI agent (LangGraph)"

        graph = create_modernize_graph()
        state = graph.invoke({"raw_requirement": user_req})

        # Check if build was successful
        if state.get('build_success'):
            # Only create MR and commit changes if build was successful
            refined_req = refine_requirement(user_req)
            mr_description = generate_mr_description(refined_req, user_req)
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
            plantuml_result = generate_plantuml_diagram(code_snapshot, config)
            png_path = render_plantuml_to_png(plantuml_result)

            return jsonify({
                'success': True,
                'mr_details': mr_description,
                'mr_link': mr_url,
                'branch_name': branch_name,
                'endpoint_url': state.get('endpoint_url') if state.get('endpoint_health') else None,
                'endpoint_health': state.get('endpoint_health'),
                'actuator_health_url': state.get('actuator_health_url') if state.get('endpoint_health') else None,
                'plantuml_png': png_path
            })
        else:
            # Build failed - return error without creating MR
            return jsonify({
                'success': False,
                'error': 'Build verification failed - merge request not created',
                'build_output': state.get('build_output', 'No build output available'),
                'branch_name': branch_name
            }), 500

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {error_details}")
        return jsonify({'success': False, 'error': f'An error occurred: {str(e)}', 'details': error_details}), 500


@app.route('/generate_tests', methods=['POST'])
def generate_tests_for_project():
    try:
        data = request.get_json()
        if not data or 'githubRepo' not in data:
            return jsonify({'error': 'Missing githubRepo field'}), 400

        repo_path = data['githubRepo']
        if '/' not in repo_path or repo_path.count('/') != 1:
            return jsonify({'error': 'Invalid repo path format. Must be in format: username/repo-name'}), 400

        config = load_and_update_config(repo_path)
        git_handler, repo = clone_or_pull_repo(config)

        print("🧪 Starting test generation process...")

        # Create and run the test generation workflow
        test_workflow = create_test_agent_workflow()
        test_state = test_workflow.invoke({"project_path": config["repository"]["local_dir"]})

        if test_state.get('success'):
            # Generate PlantUML diagram for the codebase with tests
            code_files = get_code_files_for_summary(config["repository"]["local_dir"])
            code_snapshot = "\n\n".join(code_files)
            plantuml_result = generate_plantuml_diagram(code_snapshot, config)
            png_path = render_plantuml_to_png(plantuml_result)

            return jsonify({
                'success': True,
                'message': 'Test generation and coverage analysis complete',
                'test_files_count': len(test_state.get('test_files', [])),
                'coverage_data': test_state.get('coverage_data', {}),
                'coverage_report': test_state.get('coverage_report', 'No coverage data'),
                'report_url': test_state.get('report_url', ''),
                'plantuml_png': png_path
            })
        else:
            return jsonify({
                'success': False,
                'error': test_state.get('error', 'Test generation failed'),
                'details': test_state.get('details', '')
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


def get_code_files_for_summary(base_dir):
    """Gets all code files from the base directory for summary generation."""
    code_files = []
    for root, dirs, files in os.walk(base_dir):
        # Skip .git directory
        if '.git' in dirs:
            dirs.remove('.git')
        # Skip target directory (Maven build output)
        if 'target' in dirs:
            dirs.remove('target')
        # Skip node_modules if present
        if 'node_modules' in dirs:
            dirs.remove('node_modules')
        
        for file in files:
            if file.endswith(('.java', '.py', '.js', '.ts', '.html', '.css', '.xml', '.yml', '.yaml', '.properties', '.md')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    relative_path = os.path.relpath(file_path, base_dir)
                    code_files.append(f"File: {relative_path}\n{content}")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
    return code_files


def generate_gemini_summary(code_snapshot, config):
    """Generates a summary of the codebase using Gemini AI."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model=config["gemini"]["model"],
        google_api_key=config["gemini"]["api_key"],
        temperature=0.1
    )
    
    prompt = f"""
    Analyze the following codebase and provide a comprehensive summary in bullet points.
    Focus on:
    - Main components and their purposes
    - Technology stack used
    - Key functionality
    - Architecture patterns
    - Dependencies and frameworks
    
    Codebase:
    {code_snapshot}
    
    Provide a clear, structured summary with bullet points.
    """
    
    response = llm.invoke(prompt)
    return response.content


def generate_plantuml_diagram(code_snapshot, config):
    """Generates a PlantUML diagram of the codebase architecture."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model=config["gemini"]["model"],
        google_api_key=config["gemini"]["api_key"],
        temperature=0.1
    )
    
    prompt = f"""
    Analyze the following codebase and generate a PlantUML class diagram showing the main components, classes, and their relationships.
    Focus on:
    - Main classes and their methods
    - Relationships between classes (inheritance, composition, association)
    - Key interfaces and abstract classes
    - Package structure if applicable
    
    Codebase:
    {code_snapshot}
    
    Generate only the PlantUML diagram code (without @startuml/@enduml tags).
    """
    
    response = llm.invoke(prompt)
    return response.content


@app.route('/summarize', methods=['POST'])
def summarize_project():
    try:
        data = request.get_json()
        if not data or 'githubRepo' not in data:
            return jsonify({'error': 'Missing githubRepo field'}), 400

        repo_path = data['githubRepo']
        if '/' not in repo_path or repo_path.count('/') != 1:
            return jsonify({'error': 'Invalid repo path format. Must be in format: username/repo-name'}), 400

        config = load_and_update_config(repo_path)
        git_handler, repo = clone_or_pull_repo(config)

        print("📊 Generating codebase summary and diagram...")

        # Get all code files
        code_files = get_code_files_for_summary(config["repository"]["local_dir"])
        if not code_files:
            return jsonify({'error': 'No code files found in the repository'}), 404

        code_snapshot = "\n\n".join(code_files)

        # Generate summary
        summary = generate_gemini_summary(code_snapshot, config)

        # Generate PlantUML diagram
        plantuml_result = generate_plantuml_diagram(code_snapshot, config)
        png_path = render_plantuml_to_png(plantuml_result)

        return jsonify({
            'summary': summary,
            'plantuml_png': png_path
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500


@app.route('/diagrams/<filename>')
def serve_diagram(filename):
    """Serves generated PlantUML diagram images."""
    return send_from_directory('diagrams', filename)


@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Manually clean up temporary directories and files without shutting down the server."""
    try:
        data = request.get_json() or {}
        force_cleanup = data.get('force', False)
        
        print("🧹 Starting manual cleanup...")
        
        # Get cleanup status first
        from utils.cleanup import get_cleanup_status
        status = get_cleanup_status()
        
        # Perform cleanup
        cleaned_folders = cleanup_directories(force_cleanup=force_cleanup)
        
        return jsonify({
            'success': True,
            'message': 'Cleanup completed successfully',
            'cleaned_folders': cleaned_folders,
            'force_cleanup': force_cleanup
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error during manual cleanup: {str(e)}")
        print(f"Traceback: {error_details}")
        
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}',
            'details': error_details
        }), 500


@app.route('/cleanup/status', methods=['GET'])
def get_cleanup_status():
    """Get the current status of directories that would be cleaned up."""
    try:
        from utils.cleanup import get_cleanup_status as get_status
        status = get_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error getting cleanup status: {str(e)}")
        print(f"Traceback: {error_details}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to get cleanup status: {str(e)}',
            'details': error_details
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'Agentic AI API is running'
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
