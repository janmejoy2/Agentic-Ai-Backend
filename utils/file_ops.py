import os
import shutil
from typing import List, Dict, Any


def apply_structured_changes(file_instructions: List[Dict[str, Any]], repo_dir: str) -> None:
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
                f.write(file.get("content", ""))
            print(f"Written: {path}")


def cleanup_legacy_java_files(repo_dir: str) -> List[str]:
    """
    Identify and clean up legacy Java files that are commonly left behind during modernization.
    Returns list of deleted files.
    """
    deleted_files = []
    
    # Common legacy patterns to look for
    legacy_patterns = [
        # Old test directories
        "src/test/java",
        # Legacy configuration files
        "src/main/webapp/WEB-INF/web.xml",
        "src/main/resources/application.properties",
        "src/main/resources/application.yml",
        # Old build files
        "build.xml",
        "ant.properties",
        # IDE files
        ".idea",
        ".vscode",
        "*.iml",
        # Backup files
        "*.bak",
        "*.backup",
        "*.old",
        # Temporary files
        "*.tmp",
        "*.temp"
    ]
    
    # Walk through the repository
    for root, dirs, files in os.walk(repo_dir):
        # Check directories
        for dir_name in dirs[:]:  # Copy list to avoid modification during iteration
            dir_path = os.path.join(root, dir_name)
            rel_path = os.path.relpath(dir_path, repo_dir)
            
            # Remove legacy directories
            if any(pattern in rel_path for pattern in ["src/test/java", ".idea", ".vscode"]):
                try:
                    shutil.rmtree(dir_path)
                    deleted_files.append(rel_path)
                    print(f"🧹 Cleaned up legacy directory: {rel_path}")
                except Exception as e:
                    print(f"⚠️ Could not remove directory {rel_path}: {e}")
        
        # Check files
        for file_name in files:
            file_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(file_path, repo_dir)
            
            # Remove legacy files
            if any(pattern in rel_path for pattern in [
                "web.xml", "build.xml", "ant.properties", 
                ".iml", ".bak", ".backup", ".old", ".tmp", ".temp"
            ]):
                try:
                    os.remove(file_path)
                    deleted_files.append(rel_path)
                    print(f"🧹 Cleaned up legacy file: {rel_path}")
                except Exception as e:
                    print(f"⚠️ Could not remove file {rel_path}: {e}")
    
    return deleted_files


def detect_modernization_deletions(repo_dir: str) -> List[str]:
    """
    Intelligently detect files that should be deleted after modernization.
    This function looks for common patterns of files that are no longer needed.
    """
    import os
    
    files_to_delete = []
    
    # Common patterns of files that should be deleted during modernization
    deletion_patterns = [
        # Old test files
        "src/test/java",
        # Legacy web.xml
        "src/main/webapp/WEB-INF/web.xml",
        # Old properties files
        "src/main/resources/application.properties",
        "src/main/resources/application.yml",
        # Old build files
        "build.xml",
        "ant.properties",
        # Old servlet classes (if modernizing to Spring Boot)
        "**/Servlet.java",
        "**/DAO.java",
        # Old test classes
        "**/Test.java",
        "**/Tests.java"
    ]
    
    # Walk through the repository to find files matching deletion patterns
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_dir).replace(os.sep, '/')
            
            # Check if this file matches any deletion pattern
            should_delete = False
            for pattern in deletion_patterns:
                if pattern.endswith('/**'):
                    # Pattern like "src/test/java/**"
                    base_pattern = pattern[:-3]
                    if rel_path.startswith(base_pattern):
                        should_delete = True
                        break
                elif pattern.startswith('**/'):
                    # Pattern like "**/Servlet.java"
                    suffix = pattern[3:]
                    if rel_path.endswith(suffix):
                        should_delete = True
                        break
                elif pattern in rel_path:
                    # Direct pattern match
                    should_delete = True
                    break
            
            if should_delete:
                files_to_delete.append(rel_path)
                print(f"🎯 Marked for deletion: {rel_path}")
    
    return files_to_delete


def ensure_gitignore_excludes_target(repo_dir: str) -> None:
    """
    Ensure the .gitignore file properly excludes target directory and other unwanted files.
    This function creates or updates .gitignore to prevent future tracking of unwanted files.
    """
    import os
    
    gitignore_path = os.path.join(repo_dir, ".gitignore")
    
    # Content to ensure is in .gitignore
    required_exclusions = [
        "# Build directories",
        "target/",
        "build/",
        "out/",
        "bin/",
        "classes/",
        "",
        "# Backup files",
        "*.bak",
        "*.backup",
        "*.old",
        "*.tmp",
        "*.temp",
        "",
        "# IDE files",
        ".idea/",
        ".vscode/",
        "*.iml",
        "*.ipr",
        "*.iws",
        "",
        "# Application files (this backend)",
        "app.py",
        "requirements.txt",
        "integration.yml",
        "",
        "# OS files",
        ".DS_Store",
        "Thumbs.db",
        "*.lnk"
    ]
    
    try:
        # Read existing .gitignore if it exists
        existing_content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # Check if required exclusions are already present
        missing_exclusions = []
        for exclusion in required_exclusions:
            if exclusion.startswith('#'):
                # Comment line, just check if it exists
                if exclusion not in existing_content:
                    missing_exclusions.append(exclusion)
            elif exclusion and not exclusion.startswith('#'):
                # Actual exclusion pattern
                if exclusion not in existing_content:
                    missing_exclusions.append(exclusion)
        
        if missing_exclusions:
            print(f"🔧 Updating .gitignore with missing exclusions...")
            
            # Add missing exclusions
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                f.write("\n# Auto-added by modernization process\n")
                for exclusion in missing_exclusions:
                    f.write(exclusion + "\n")
            
            print(f"✅ Updated .gitignore with {len(missing_exclusions)} exclusions")
        else:
            print("✅ .gitignore already contains all required exclusions")
            
    except Exception as e:
        print(f"⚠️ Could not update .gitignore: {e}")


def aggressively_clean_target_directory(repo_dir: str) -> None:
    """
    Aggressively clean up the target directory and ensure it's completely removed from Git.
    This function handles cases where target directory might be tracked by Git.
    """
    import git
    import os
    import shutil
    
    try:
        repo = git.Repo(repo_dir)
        target_path = os.path.join(repo_dir, "target")
        
        if os.path.exists(target_path):
            print(f"🧹 Aggressively cleaning target directory: {target_path}")
            
            # First, remove from Git index if tracked
            try:
                # Check if target directory is tracked by Git
                tracked_files = repo.git.ls_files("target/")
                if tracked_files:
                    print(f"📁 Target directory has {len(tracked_files.splitlines())} tracked files")
                    
                    # Remove all tracked files in target directory
                    for line in tracked_files.splitlines():
                        if line.strip():
                            try:
                                repo.git.rm("--cached", "-r", line.strip())
                                print(f"✅ Removed from Git index: {line.strip()}")
                            except git.GitCommandError as e:
                                print(f"⚠️ Could not remove {line.strip()} from index: {e}")
                    
                    # Remove the target directory itself from Git
                    try:
                        repo.git.rm("--cached", "-r", "target/")
                        print("✅ Removed target/ directory from Git index")
                    except git.GitCommandError as e:
                        print(f"⚠️ Could not remove target/ directory from index: {e}")
                else:
                    print("ℹ️ Target directory not tracked by Git")
            except git.GitCommandError:
                print("ℹ️ Target directory not tracked by Git")
            
            # Now physically remove the target directory
            try:
                shutil.rmtree(target_path)
                print(f"✅ Physically removed target directory: {target_path}")
            except Exception as e:
                print(f"⚠️ Could not physically remove target directory: {e}")
        else:
            print("ℹ️ Target directory does not exist")
            
    except Exception as e:
        print(f"⚠️ Target directory cleanup failed: {e}")


def force_git_cleanup(repo_dir: str) -> None:
    """
    Force Git to recognize deleted files by resetting and re-adding.
    This is a more aggressive approach to ensure deletions are tracked.
    """
    import git
    import subprocess
    import os
    
    try:
        repo = git.Repo(repo_dir)
        
        # First, aggressively clean the target directory
        aggressively_clean_target_directory(repo_dir)
        
        # Get current branch
        current_branch = repo.active_branch.name
        
        # Get all tracked files from the current branch
        tracked_files = set(repo.git.ls_tree(current_branch, '--name-only', '-r').splitlines())
        
        # Get current working directory files
        working_files = set()
        for root, dirs, files in os.walk(repo_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), repo_dir).replace(os.sep, '/')
                working_files.add(rel_path)
        
        # Find deleted files (tracked but not in working directory)
        deleted_files = tracked_files - working_files
        
        # Also detect files that should be deleted based on modernization patterns
        modernization_deletions = detect_modernization_deletions(repo_dir)
        
        if deleted_files or modernization_deletions:
            print(f"🧹 Force Git cleanup: Found {len(deleted_files)} deleted files and {len(modernization_deletions)} modernization deletions")
            
            # Instead of git add -A, selectively add only source files
            try:
                # Reset to clean state
                repo.git.reset('HEAD')
                print("✅ Git reset completed")
                
                # Add only source code and config files, exclude unwanted files
                for root, dirs, files in os.walk(repo_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_dir).replace(os.sep, '/')
                        
                        # Skip files we don't want to commit
                        if (rel_path.endswith('.bak') or 
                            rel_path.endswith('.backup') or 
                            rel_path.endswith('.old') or
                            rel_path.startswith('target/') or
                            rel_path == 'app.py' or
                            rel_path == 'requirements.txt' or
                            '.idea/' in rel_path or
                            '.vscode/' in rel_path or
                            rel_path.endswith('.iml') or
                            rel_path.endswith('.tmp') or
                            rel_path.endswith('.temp')):
                            continue
                        
                        # Add only source code and config files
                        if (rel_path.endswith(('.java', '.xml', '.yml', '.yaml', '.properties', '.md', '.txt')) or
                            rel_path.startswith('src/') or
                            rel_path.startswith('pom.xml')):
                            try:
                                repo.index.add([rel_path])
                                print(f"✅ Added to index: {rel_path}")
                            except Exception as e:
                                print(f"⚠️ Could not add {rel_path}: {e}")
                
                # Handle deletions specifically - only for files that are actually tracked
                for deleted_file in deleted_files:
                    try:
                        # Check if the file is actually tracked by Git before trying to remove it
                        if deleted_file in tracked_files:
                            # Use git rm to remove from both index and working tree
                            repo.git.rm(deleted_file)
                            print(f"✅ Force removed {deleted_file} from Git")
                        else:
                            print(f"ℹ️ Skipping {deleted_file} - not tracked by Git")
                    except git.GitCommandError as e:
                        print(f"⚠️ Could not force remove {deleted_file}: {e}")
                
                # Handle modernization deletions
                for deletion in modernization_deletions:
                    if deletion in tracked_files:
                        try:
                            repo.git.rm(deletion)
                            print(f"✅ Force removed modernization deletion: {deletion}")
                        except git.GitCommandError as e:
                            print(f"⚠️ Could not remove modernization deletion {deletion}: {e}")
                    else:
                        print(f"ℹ️ Modernization deletion {deletion} not tracked by Git")
                        
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Git operations failed: {e}")
        else:
            print("✅ No deleted files found during force cleanup")
            
    except Exception as e:
        print(f"⚠️ Force Git cleanup failed: {e}")


def ensure_clean_modernization(repo_dir: str) -> None:
    """
    Ensure the repository is properly cleaned up after modernization.
    This function should be called after applying structured changes.
    """
    print("🧹 Performing post-modernization cleanup...")
    
    # Clean up legacy files
    deleted_files = cleanup_legacy_java_files(repo_dir)
    
    if deleted_files:
        print(f"✅ Cleaned up {len(deleted_files)} legacy files/directories")
        print("Deleted items:", deleted_files)
    else:
        print("✅ No legacy files found to clean up")
    
    # Additional cleanup: remove empty directories
    for root, dirs, files in os.walk(repo_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # Directory is empty
                    os.rmdir(dir_path)
                    print(f"🧹 Removed empty directory: {os.path.relpath(dir_path, repo_dir)}")
            except Exception:
                pass  # Directory not empty or permission denied
    
    # Ensure .gitignore properly excludes unwanted files
    print("🔧 Ensuring .gitignore excludes unwanted files...")
    ensure_gitignore_excludes_target(repo_dir)
    
    # Force Git to recognize all changes including deletions
    print("🔧 Force Git cleanup...")
    force_git_cleanup(repo_dir)

