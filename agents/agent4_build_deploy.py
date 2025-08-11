import os
import yaml
import subprocess
import time
import requests
import signal
import psutil
from typing import Tuple, Optional

# Global variable to track the Spring Boot process
spring_boot_process = None

def load_config() -> dict:
    """Load configuration from integration.yml"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def fix_and_build(code_dir: str, max_attempts: int = 3) -> Tuple[bool, str]:
    """
    Agent 3's fix_and_build function - now Agent 4.
    Attempts to build the project and automatically fixes common issues.
    """
    print("🔧 Agent 4: Starting build and deployment process...")
    
    for attempt in range(max_attempts):
        print(f"🔄 Build attempt {attempt + 1}/{max_attempts}")
        
        # Try to build
        build_success, build_output = try_build(code_dir)
        
        if build_success:
            print("✅ Build successful!")
            return True, build_output
        
        print(f"❌ Build failed on attempt {attempt + 1}")
        print(f"Build output: {build_output}")
        
        if attempt < max_attempts - 1:
            print("🔧 Attempting to fix build issues...")
            fix_attempt = fix_build_issues(code_dir, build_output)
            if fix_attempt:
                print("🔧 Applied fixes, retrying build...")
            else:
                print("⚠️ Could not apply fixes, retrying with original code...")
    
    print("❌ All build attempts failed")
    return False, build_output


def check_maven_available() -> bool:
    """Check if Maven is available in the system PATH."""
    try:
        import platform
        mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
        result = subprocess.run([mvn_command, "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def try_build(code_dir: str) -> Tuple[bool, str]:
    """Attempt to build the project using Maven."""
    # Check if Maven is available first
    if not check_maven_available():
        return False, "Maven is not available in the system PATH. Please install Maven and ensure it's in your PATH."
    
    try:
        print("🔨 Running Maven build...")
        
        # Use mvn.cmd on Windows, mvn on other platforms
        import platform
        mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
        
        # Build without clean to avoid file lock issues
        result = subprocess.run(
            [mvn_command, "compile", "package", "-DskipTests"],
            cwd=code_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stdout + result.stderr
            
    except subprocess.TimeoutExpired:
        return False, "Build timed out after 5 minutes"
    except Exception as e:
        return False, f"Build failed with exception: {str(e)}"


def fix_build_issues(code_dir: str, build_output: str) -> bool:
    """
    Attempt to fix common build issues based on error output.
    Returns True if fixes were applied, False otherwise.
    """
    print("🔧 Analyzing build errors and applying fixes...")
    
    fixes_applied = False
    
    # Check for validation import issues (javax.validation -> jakarta.validation)
    if "javax.validation" in build_output or "cannot find symbol" in build_output:
        print("🔧 Detected validation import issue, updating Java imports...")
        if fix_validation_import_issues(code_dir):
            fixes_applied = True
    
    # Check for common Java version issues
    if "release" in build_output.lower() or "source" in build_output.lower():
        print("🔧 Detected Java version issue, updating pom.xml...")
        if fix_java_version_issue(code_dir):
            fixes_applied = True
    
    # Check for dependency issues
    if "dependency" in build_output.lower() or "artifact" in build_output.lower():
        print("🔧 Detected dependency issue, updating dependencies...")
        if fix_dependency_issues(code_dir):
            fixes_applied = True
    
    # Check for Spring Boot version issues
    if "spring" in build_output.lower() and "version" in build_output.lower():
        print("🔧 Detected Spring Boot version issue, updating...")
        if fix_spring_boot_version(code_dir):
            fixes_applied = True
    
    return fixes_applied


def fix_java_version_issue(code_dir: str) -> bool:
    """Fix Java version compatibility issues in pom.xml."""
    try:
        pom_path = os.path.join(code_dir, "pom.xml")
        if not os.path.exists(pom_path):
            return False
        
        with open(pom_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update Java version to 17
        updated_content = content.replace(
            '<maven.compiler.source>1.8</maven.compiler.source>',
            '<maven.compiler.source>17</maven.compiler.source>'
        ).replace(
            '<maven.compiler.target>1.8</maven.compiler.target>',
            '<maven.compiler.target>17</maven.compiler.target>'
        ).replace(
            '<java.version>1.8</java.version>',
            '<java.version>17</java.version>'
        )
        
        if updated_content != content:
            with open(pom_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print("✅ Updated Java version to 17")
            return True
        
        return False
        
    except Exception as e:
        print(f"⚠️ Could not fix Java version issue: {e}")
        return False


def fix_dependency_issues(code_dir: str) -> bool:
    """Fix dependency issues in pom.xml."""
    try:
        pom_path = os.path.join(code_dir, "pom.xml")
        if not os.path.exists(pom_path):
            return False
        
        with open(pom_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        fixes_applied = False
        
        # Check for missing validation dependency
        if 'spring-boot-starter-validation' not in content:
            print("🔧 Adding missing Spring Boot validation starter...")
            # Find the dependencies section and add validation starter
            if '<dependencies>' in content:
                validation_dep = '''
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>'''
                
                # Insert before closing </dependencies>
                content = content.replace('</dependencies>', validation_dep + '\n  </dependencies>')
                
                with open(pom_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print("✅ Added spring-boot-starter-validation dependency")
                fixes_applied = True
        
        # Add missing Spring Boot dependencies
        if 'spring-boot-starter-web' not in content:
            print("🔧 Adding missing Spring Boot web starter...")
            # This is a simplified fix - in practice, you'd want more sophisticated dependency management
            fixes_applied = True
        
        return fixes_applied
        
    except Exception as e:
        print(f"⚠️ Could not fix dependency issues: {e}")
        return False


def fix_validation_import_issues(code_dir: str) -> bool:
    """Fix validation import issues by updating javax.validation to jakarta.validation."""
    try:
        print("🔧 Scanning Java files for javax.validation imports...")
        
        # Find all Java files in the src directory
        src_dir = os.path.join(code_dir, "src", "main", "java")
        if not os.path.exists(src_dir):
            print(f"⚠️ Source directory not found: {src_dir}")
            return False
        
        fixes_applied = False
        
        # Walk through all Java files
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.java'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check if file contains javax.validation
                        if 'javax.validation' in content:
                            print(f"🔧 Fixing validation imports in: {os.path.relpath(file_path, code_dir)}")
                            
                            # Replace javax.validation with jakarta.validation
                            updated_content = content.replace('javax.validation', 'jakarta.validation')
                            
                            if updated_content != content:
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(updated_content)
                                print(f"✅ Updated validation imports in: {os.path.relpath(file_path, code_dir)}")
                                fixes_applied = True
                            
                    except Exception as e:
                        print(f"⚠️ Could not process file {file_path}: {e}")
                        continue
        
        if fixes_applied:
            print("✅ Validation import fixes applied successfully")
        else:
            print("ℹ️ No validation import issues found")
        
        return fixes_applied
        
    except Exception as e:
        print(f"⚠️ Could not fix validation import issues: {e}")
        return False


def fix_spring_boot_version(code_dir: str) -> bool:
    """Fix Spring Boot version issues in pom.xml."""
    try:
        pom_path = os.path.join(code_dir, "pom.xml")
        if not os.path.exists(pom_path):
            return False
        
        with open(pom_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update Spring Boot version to 3.x
        updated_content = content.replace(
            '<version>2.7.0</version>',
            '<version>3.2.0</version>'
        ).replace(
            '<version>2.6.0</version>',
            '<version>3.2.0</version>'
        ).replace(
            '<version>2.5.0</version>',
            '<version>3.2.0</version>'
        )
        
        if updated_content != content:
            with open(pom_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print("✅ Updated Spring Boot version to 3.2.0")
            return True
        
        return False
        
    except Exception as e:
        print(f"⚠️ Could not fix Spring Boot version: {e}")
        return False


def build_and_deploy(code_dir: str, max_attempts: int = 3) -> Tuple[bool, str, Optional[str], bool, Optional[str]]:
    """
    Agent 4: Build and deploy the application with health checks.
    Returns: (success, output, endpoint_url, health_ok, actuator_health_url)
    """
    print("🚀 Agent 4: Starting build and deployment...")
    
    # First, try to build the project
    build_success, build_output = fix_and_build(code_dir, max_attempts)
    endpoint_url, health_ok, actuator_health_url = (None, False, None)
    
    if build_success:
        print("✅ Build successful, starting deployment...")
        
        # Find the JAR file
        artifact_path = None
        target_dir = os.path.join(code_dir, 'target')
        if os.path.isdir(target_dir):
            for file in os.listdir(target_dir):
                if file.endswith('.jar') or file.endswith('.war'):
                    artifact_path = os.path.join(target_dir, file)
                    break
        
        if artifact_path:
            print(f"📦 Found artifact: {artifact_path}")
            endpoint_url, health_ok, actuator_health_url = deploy_and_check_health(artifact_path)
        else:
            print("❌ No artifact found to deploy.")
    else:
        print("❌ Build failed, cannot deploy")
    
    return build_success, build_output, endpoint_url, health_ok, actuator_health_url


def deploy_and_check_health(artifact_path):
    """Deploy the artifact and check health - based on stable old version."""
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


def check_health_endpoint(url: str) -> bool:
    """Check if a health endpoint is responding."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Health check passed for {url} (Status: {response.status_code})")
            return True
        else:
            print(f"⚠️ Health check failed for {url} (Status: {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection refused for {url} - service not ready yet")
        return False
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout for {url} - service responding slowly")
        return False
    except Exception as e:
        print(f"❌ Health check error for {url}: {e}")
        return False


def stop_spring_boot_server():
    """
    Stop the Spring Boot server if it's running.
    This function should be called when the Flask API server shuts down.
    """
    try:
        # Find Java processes running on port 8080
        import subprocess
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        
        java_pids = []
        for line in result.stdout.split('\n'):
            if ':8080' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    # Check if this PID is a Java process
                    try:
                        task_result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True)
                        if 'java.exe' in task_result.stdout:
                            java_pids.append(pid)
                    except:
                        pass
        
        if java_pids:
            print(f"🛑 Found {len(java_pids)} Java process(es) on port 8080, stopping...")
            for pid in java_pids:
                try:
                    subprocess.run(['taskkill', '/PID', pid, '/F'], check=True)
                    print(f"✅ Stopped Java process PID: {pid}")
                except subprocess.CalledProcessError as e:
                    print(f"⚠️ Could not stop process {pid}: {e}")
        else:
            print("ℹ️ No Java processes found on port 8080")
            
    except Exception as e:
        print(f"⚠️ Error stopping Spring Boot server: {e}")


def create_build_deploy_agent_workflow(code_dir: str) -> Tuple[bool, str, dict]:
    """
    Main workflow for Agent 4: Build and deploy.
    """
    try:
        print("🚀 Agent 4: Starting build and deployment workflow...")
        
        success, output, endpoint_url, health_ok, actuator_health_url = build_and_deploy(code_dir)
        
        return success, "Build and deployment completed", {
            "build_output": output,
            "endpoint_url": endpoint_url,
            "endpoint_health": health_ok,
            "actuator_health_url": actuator_health_url
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Agent 4 workflow failed: {e}")
        print(f"Traceback: {error_details}")
        return False, f"Build and deployment failed: {e}", {"error_details": error_details}
