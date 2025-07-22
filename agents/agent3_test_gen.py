import subprocess
import yaml
import json
import re
import os
import shutil
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Tuple, List, Dict, Optional, Callable

# Load configuration
# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the parent directory and find integration.yml
config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")

with open(config_path) as f:
    config = yaml.safe_load(f)
GEMINI_API_KEY = config["gemini"]["api_key"]
GEMINI_MODEL = config["gemini"]["model"]
LOCAL_REPO_DIR = config["repository"]["local_dir"]

def check_maven_available() -> bool:
    """
    Check if Maven is available in the system PATH
    """
    try:
        import platform
        mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
        result = subprocess.run([mvn_command, "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def run_maven_compile(code_dir: str) -> Tuple[bool, str, str]:
    """
    Run 'mvn clean compile' and return (success, stdout, stderr)
    """
    import platform
    mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
    try:
        print(f"🔨 Running Maven clean compile in directory: {code_dir}")
        result = subprocess.run(
            [mvn_command, "clean", "compile"],
            cwd=code_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Maven compile timed out after 5 minutes"
    except Exception as e:
        return False, "", f"Maven compile failed with exception: {str(e)}"

def run_maven_package(code_dir: str) -> tuple[bool, str, str]:
    """
    Run 'mvn package' and return (success, stdout, stderr)
    """
    import platform
    mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
    try:
        print(f"📦 Running Maven package in directory: {code_dir}")
        result = subprocess.run(
            [mvn_command, "package"],
            cwd=code_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Maven package timed out after 5 minutes"
    except Exception as e:
        return False, "", f"Maven package failed with exception: {str(e)}"

def extract_build_errors(output: str) -> List[Dict]:
    """
    Extract meaningful build errors from Maven output (stdout + stderr)
    """
    errors = []
    # Compilation errors
    compilation_pattern = r'\[ERROR\] (.+\.java):\[(\d+),(\d+)\] (.+)'
    compilation_matches = re.findall(compilation_pattern, output)
    for match in compilation_matches:
        file_path, line, column, error_msg = match
        errors.append({
            "type": "compilation",
            "file": file_path,
            "line": int(line),
            "column": int(column),
            "message": error_msg.strip()
        })
    # Dependency issues
    dependency_pattern = r'\[ERROR\] (.+\.jar) was not found'
    dependency_matches = re.findall(dependency_pattern, output)
    for match in dependency_matches:
        errors.append({
            "type": "dependency",
            "message": f"Missing dependency: {match}"
        })
    # General Maven errors
    general_error_pattern = r'\[ERROR\] (.+)'
    general_matches = re.findall(general_error_pattern, output)
    for match in general_matches:
        if match not in [error.get("message", "") for error in errors]:
            errors.append({
                "type": "general",
                "message": match.strip()
            })
    return errors

def get_file_content(file_path: str, code_dir: str) -> Optional[str]:
    """
    Get the content of a specific file
    """
    try:
        # Use file_path as is if absolute, else join with code_dir
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(code_dir, file_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return None

def fix_build_errors(errors: List[Dict], code_dir: str) -> List[Dict]:
    """
    Use LLM to fix build errors and return the fixes
    """
    if not errors:
        return []
    
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY)
    
    # Collect relevant file contents
    files_to_fix = set()
    for error in errors:
        if error.get("file"):
            files_to_fix.add(error["file"])
    
    file_contents = {}
    for file_path in files_to_fix:
        content = get_file_content(file_path, code_dir)
        if content:
            file_contents[file_path] = content
    
    # Create error summary
    error_summary = "\n".join([
        f"- {error['type']}: {error.get('file', 'N/A')}:{error.get('line', 'N/A')} - {error['message']}"
        for error in errors
    ])
    
    # Create file content summary
    files_summary = ""
    for file_path, content in file_contents.items():
        files_summary += f"\n// FILE: {file_path}\n{content}\n"
    
    prompt = (
        "You are an expert Java developer. The Maven build step is failing with the following errors:\n\n"
        f"{error_summary}\n\n"
        "Here are the relevant files that need to be fixed:\n"
        f"{files_summary}\n\n"
        "Please fix these build errors. Return ONLY a JSON response with the following format:\n\n"
        "{\n"
        "  \"files\": [\n"
        "    {\n"
        "      \"path\": \"src/main/java/com/example/Foo.java\",\n"
        "      \"action\": \"update\",\n"
        "      \"content\": \"...fixed code...\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "IMPORTANT: Always use RELATIVE paths for the 'path' field (relative to the project root). Never use absolute paths.\n"
        "Focus on:\n"
        "1. Fixing compilation errors (missing imports, syntax errors, etc.)\n"
        "2. Resolving dependency issues in pom.xml\n"
        "3. Ensuring code compiles and runs successfully\n"
        "DO NOT return markdown, comments, or explanations. Only return the JSON."
    )
    
    try:
        response = llm.invoke(prompt)
        raw_output = str(response.content).strip()
        
        # Clean up the response
        if raw_output.startswith("```json"):
            raw_output = raw_output.lstrip("```json").rstrip("```").strip()
        elif raw_output.startswith("```"):
            raw_output = raw_output.lstrip("```").rstrip("```").strip()
        
        parsed = json.loads(raw_output)
        return parsed.get("files", [])
        
    except Exception as e:
        print(f"❌ Failed to get fixes from LLM: {e}")
        return []

def apply_fixes(fixes: List[Dict], code_dir: str) -> bool:
    """
    Apply the fixes returned by the LLM
    """
    if not fixes:
        return False
    
    try:
        for fix in fixes:
            file_path = os.path.normpath(fix["path"])
            # Handle absolute/relative paths
            if not os.path.isabs(file_path):
                full_path = os.path.abspath(os.path.join(code_dir, file_path))
            else:
                full_path = file_path
            # Ensure file is within project
            if not full_path.startswith(os.path.abspath(code_dir)):
                print(f"❌ Refusing to write outside project: {full_path}")
                continue
            # Backup before overwrite
            if os.path.exists(full_path) and fix["action"] in ("update", "delete"):
                shutil.copy2(full_path, full_path + ".bak")
            action = fix["action"]
            content = fix.get("content", "")
            
            if action == "update":
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Updated {file_path}")
            elif action == "create":
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Created {file_path}")
            elif action == "delete":
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"✅ Deleted {file_path}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to apply fixes: {e}")
        return False

def fix_and_build(code_dir: str, max_attempts: int = 3, on_success: Optional[Callable]=None) -> tuple[bool, str]:
    """
    Try to build with 'mvn clean compile', then 'mvn package', auto-fix with LLM if either fails, and call on_success if both pass.
    Returns (success, build_output)
    """
    if not check_maven_available():
        return False, "Maven is not available in the system PATH. Please install Maven and ensure it's in your PATH."
    for attempt in range(max_attempts):
        print(f"\n📋 Attempt {attempt + 1}/{max_attempts}")
        build_success, stdout, stderr = run_maven_compile(code_dir)
        output = stdout + "\n" + stderr
        if build_success:
            print("✅ Build (mvn clean compile) successful!")
            # Run mvn package after successful build
            package_success, package_stdout, package_stderr = run_maven_package(code_dir)
            package_output = package_stdout + "\n" + package_stderr
            if package_success:
                print("✅ Maven package successful!")
                if on_success:
                    on_success()
                return True, output + "\n" + package_output
            else:
                print("❌ Maven package failed. Parsing errors and sending to LLM...")
                errors = extract_build_errors(package_output)
                if errors:
                    fixes = fix_build_errors(errors, code_dir)
                    if fixes:
                        print(f"🔧 Applying {len(fixes)} fixes for package errors...")
                        if apply_fixes(fixes, code_dir):
                            print("✅ Fixes applied. Retrying build and package...")
                            continue
                        else:
                            print("❌ Failed to apply fixes for package errors. Retrying build and package anyway...")
                            continue
                    else:
                        print("❌ LLM did not generate fixes for package errors. Retrying build and package anyway...")
                        continue
                else:
                    print("❌ Could not extract specific package errors. Retrying build and package anyway...")
                    continue
        else:
            print("❌ Build failed. Parsing errors and sending to LLM...")
            errors = extract_build_errors(output)
            if errors:
                fixes = fix_build_errors(errors, code_dir)
                if fixes:
                    print(f"🔧 Applying {len(fixes)} fixes...")
                    if apply_fixes(fixes, code_dir):
                        print("✅ Fixes applied. Retrying build...")
                        continue
                    else:
                        print("❌ Failed to apply fixes. Retrying build anyway...")
                        continue
                else:
                    print("❌ LLM did not generate fixes. Retrying build anyway...")
                    continue
            else:
                print("❌ Could not extract specific build errors. Retrying build anyway...")
                continue
    print("❌ Build or package failed after max attempts.")
    return False, output

def deploy_and_check_health(artifact_path):
    import shutil, subprocess, time, requests, os
    endpoint_url = None
    deployment_type = None
    health_ok = False
    log_file_path = os.path.join(os.path.dirname(artifact_path), "deployment.log")
    health_url_found = None

    if artifact_path:
        if artifact_path.endswith('.war'):
            # Deploy WAR to Tomcat
            tomcat_webapps = '/usr/local/tomcat/webapps'
            artifact_name = os.path.splitext(os.path.basename(artifact_path))[0]
            deployed_path = os.path.join(tomcat_webapps, os.path.basename(artifact_path))
            try:
                shutil.copy2(artifact_path, deployed_path)
                deployment_type = 'war'
                endpoint_url = f'http://localhost:8080/{artifact_name}/'
                # Optionally restart Tomcat here if needed
            except Exception as e:
                print(f'Failed to deploy WAR: {e}')
        elif artifact_path.endswith('.jar'):
            # Run JAR in background and log output
            try:
                with open(log_file_path, "w") as log_file:
                    subprocess.Popen(['java', '-jar', artifact_path, '--server.port=8080'], stdout=log_file, stderr=subprocess.STDOUT)
                deployment_type = 'jar'
                endpoint_url = 'http://localhost:8080/'
            except Exception as e:
                print(f'Failed to run JAR: {e}')
                with open(log_file_path, "a") as log_file:
                    log_file.write(f"\nFailed to start JAR process: {e}")

    # --- Health check logic ---
    if endpoint_url:
        # Check both /actuator/health and /health
        health_endpoints = ['/actuator/health', '/health']
        print(f"Waiting for application to start at {endpoint_url}...")
        for _ in range(30):  # Wait up to 30 seconds
            for endpoint in health_endpoints:
                health_url = endpoint_url.rstrip('/') + endpoint
                try:
                    resp = requests.get(health_url, timeout=2)
                    if resp.status_code == 200:
                        health_ok = True
                        health_url_found = health_url
                        print(f"✅ Health check passed at: {health_url_found}")
                        break
                except requests.exceptions.RequestException:
                    pass
            if health_ok:
                break
            time.sleep(1)

        if not health_ok:
            print("❌ Health check failed. Application did not become healthy in 30 seconds.")
            print(f"Deployment logs can be found in: {log_file_path}")
            try:
                with open(log_file_path, "r") as log_file:
                    print("--- Deployment Log ---")
                    print(log_file.read())
                    print("----------------------")
            except Exception as e:
                print(f"Could not read deployment log file: {e}")

    return endpoint_url, health_ok, health_url_found

def build_and_deploy(code_dir, max_attempts=3, on_success=None):
    build_success, build_output = fix_and_build(code_dir, max_attempts, on_success)
    endpoint_url, health_ok, health_url = (None, False, None)
    if build_success:
        artifact_path = None
        target_dir = os.path.join(code_dir, 'target')
        if os.path.isdir(target_dir):
            for file in os.listdir(target_dir):
                if file.endswith('.jar') or file.endswith('.war'):
                    artifact_path = os.path.join(target_dir, file)
                    break
        if artifact_path:
            endpoint_url, health_ok, health_url = deploy_and_check_health(artifact_path)
        else:
            print("❌ No artifact found to deploy.")
    return build_success, build_output, endpoint_url, health_ok, health_url
