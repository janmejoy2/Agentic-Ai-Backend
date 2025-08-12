import os
import git
import gitlab
from datetime import datetime
from gitlab.exceptions import GitlabError
import subprocess
import signal

class AgenticGitHandler:
    def __init__(self, gitlab_url, repo_path, private_token, default_branch, local_repo_dir):
        self.gitlab_url = gitlab_url
        self.repo_path = repo_path
        self.private_token = private_token
        self.default_branch = default_branch
        self.local_repo_dir = local_repo_dir
        self.project = gitlab.Gitlab(gitlab_url, private_token=private_token).projects.get(repo_path)

    def stop_spring_server_and_cleanup(self, local_repo_dir):
        """
        Stop any running Java (Spring) server related to the repo and delete locked files.
        """
        target_dir = os.path.join(local_repo_dir, 'target')
        
        # Try to find and kill any Java process running on port 8080 (Spring Boot default)
        try:
            # Find Java processes running on port 8080
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
                print(f"[GIT] Found {len(java_pids)} Java process(es) on port 8080, stopping...")
                for pid in java_pids:
                    try:
                        subprocess.run(['taskkill', '/PID', pid, '/F'], check=True)
                        print(f"[GIT] Stopped Java process PID: {pid}")
                    except subprocess.CalledProcessError as e:
                        print(f"[GIT] Could not stop process {pid}: {e}")
            else:
                print("[GIT] No Java processes found on port 8080")
                
        except Exception as e:
            print(f"[GIT] Could not check or kill Java processes: {e}")

        # Only delete deployment log, keep the JAR file for the application to run
        deployment_log = os.path.join(target_dir, 'deployment.log')
        if os.path.exists(deployment_log):
            try:
                os.remove(deployment_log)
                print(f"[GIT] Deleted deployment log: {deployment_log}")
            except Exception as e:
                print(f"[GIT] Failed to delete deployment log: {e}")
        
        # IMPORTANT: DO NOT delete the JAR file - keep it for the application to run
        jar_file = os.path.join(target_dir, 'EmployeeServletAPI-0.0.1-SNAPSHOT.jar')
        if os.path.exists(jar_file):
            print(f"[GIT] Preserved JAR file for application: {jar_file}")
        else:
            print(f"[GIT] JAR file not found: {jar_file}")

    def clone_or_pull_repo(self):
        print(f"Cloning/pulling repository: {self.repo_path} into {self.local_repo_dir}")
        if os.path.exists(self.local_repo_dir):
            try:
                repo = git.Repo(self.local_repo_dir)
                print("[GIT] Stopping any running Spring server and cleaning up locked files...")
                self.stop_spring_server_and_cleanup(self.local_repo_dir)
                # Only clean/reset if there are uncommitted changes or untracked files
                if repo.is_dirty(untracked_files=True) or repo.untracked_files:
                    print("[GIT] Repo has uncommitted changes or untracked files. Cleaning and resetting...")
                    repo.git.reset('--hard')
                    repo.git.clean('-fd')
                else:
                    print("[GIT] Repo is already clean. No reset/clean needed.")
                print(f"[GIT] Checking out branch: {self.default_branch}")
                repo.git.checkout(self.default_branch)
                if repo.active_branch.tracking_branch() is None:
                    print(f"[GIT] Setting upstream for branch: {self.default_branch}")
                    repo.git.branch(f"--set-upstream-to=origin/{self.default_branch}", self.default_branch)
                print(f"[GIT] Pulling latest changes from origin/{self.default_branch}")
                repo.remotes.origin.pull()
                print(f"[GIT] Repository updated on branch '{self.default_branch}'.")
            except git.InvalidGitRepositoryError:
                print(f"[GIT] Directory {self.local_repo_dir} exists but is not a valid Git repository.")
                print(f"[GIT] Removing invalid directory and cloning fresh...")
                import shutil
                try:
                    shutil.rmtree(self.local_repo_dir)
                    print(f"[GIT] Successfully removed invalid directory: {self.local_repo_dir}")
                except Exception as e:
                    print(f"[GIT] Warning: Could not remove directory {self.local_repo_dir}: {e}")
                    # Try to remove just the .git directory if it exists
                    git_dir = os.path.join(self.local_repo_dir, '.git')
                    if os.path.exists(git_dir):
                        try:
                            shutil.rmtree(git_dir)
                            print(f"[GIT] Removed invalid .git directory")
                        except Exception as e2:
                            print(f"[GIT] Could not remove .git directory either: {e2}")
                            raise Exception(f"Could not clean up invalid repository directory: {e}")
                
                # Now clone fresh
                print(f"[GIT] Cloning fresh repository...")
                repo_url = f"https://oauth2:{self.private_token}@{self.gitlab_url.split('//')[1]}/{self.repo_path}.git"
                repo = git.Repo.clone_from(repo_url, self.local_repo_dir, branch=self.default_branch)
                print(f"[GIT] Repository cloned fresh on branch '{self.default_branch}'.")
            except Exception as e:
                print(f"[GIT] Error during pull: {e}")
                raise e
        else:
            print(f"[GIT] Local repo does not exist. Cloning from remote...")
            repo_url = f"https://oauth2:{self.private_token}@{self.gitlab_url.split('//')[1]}/{self.repo_path}.git"
            repo = git.Repo.clone_from(repo_url, self.local_repo_dir, branch=self.default_branch)
            print(f"[GIT] Repository cloned on branch '{self.default_branch}'.")
        return repo

    def apply_and_commit_changes(self, repo, branch_name, commit_message):
        try:
            print(f"[GIT] Checking out new branch: {branch_name}")
            repo.git.checkout('HEAD', b=branch_name)
        except git.GitCommandError as e:
            if "already exists" in str(e):
                print(f"[GIT] Branch {branch_name} already exists. Checking it out.")
                repo.git.checkout(branch_name)
            else:
                raise e

        # Get the original branch name (usually main or master)
        original_branch = self.default_branch
        
        # Get all files that were tracked in the original branch
        try:
            original_files = set(repo.git.ls_tree(original_branch, '--name-only', '-r').splitlines())
        except git.GitCommandError:
            # Fallback: if we can't get original branch files, use current tracked files
            print("[GIT] Warning: Could not get original branch files, using current tracked files")
            original_files = set(repo.git.ls_files().splitlines())
        
        # Get current working directory files
        working_files = set()
        for root, dirs, files in os.walk(self.local_repo_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), self.local_repo_dir).replace(os.sep, '/')
                working_files.add(rel_path)
        
        # Find deleted files (in original branch but not in working directory)
        deleted_files = original_files - working_files
        
        # Remove deleted files from Git index and working tree
        for deleted_file in deleted_files:
            try:
                # Check if the file is actually tracked before trying to remove it
                if deleted_file in original_files:
                    print(f"[GIT] Removing deleted file: {deleted_file}")
                    # Use git rm to remove from both index and working tree
                    repo.git.rm(deleted_file)
                else:
                    print(f"[GIT] Skipping {deleted_file} - not tracked by Git")
            except git.GitCommandError as e:
                print(f"[GIT] Warning: Could not remove {deleted_file}: {e}")
                # Try alternative approach - remove from index only
                try:
                    if deleted_file in original_files:
                        repo.git.rm("--cached", deleted_file)
                        print(f"[GIT] Removed {deleted_file} from index only")
                    else:
                        print(f"[GIT] Skipping {deleted_file} - not tracked by Git")
                except git.GitCommandError as e2:
                    print(f"[GIT] Could not remove {deleted_file} from index either: {e2}")
        
        # Get modified and new files
        changed_files = [item.a_path for item in repo.index.diff(None)] + repo.untracked_files
        # Only include files that exist on disk
        existing_files = [f for f in changed_files if os.path.exists(os.path.join(self.local_repo_dir, f))]
        
        if existing_files:
            print(f"[GIT] Adding modified/new files to index: {existing_files}")
            repo.index.add(existing_files)
        
        if deleted_files:
            print(f"[GIT] Deleted files: {list(deleted_files)}")

        # Remove .bak files from git index if any are staged
        for root, dirs, files in os.walk(self.local_repo_dir):
            for file in files:
                if file.endswith('.bak'):
                    bak_path = os.path.relpath(os.path.join(root, file), self.local_repo_dir).replace(os.sep, '/')
                    try:
                        tracked_files_list = repo.git.ls_files(bak_path)
                        if tracked_files_list:
                            print(f"[GIT] Removing .bak file from index: {bak_path}")
                            repo.git.rm("--cached", bak_path)
                    except git.GitCommandError:
                        pass
        # Handle 'target' directory - EXCLUDE FROM GIT (but keep locally)
        target_path = os.path.join(self.local_repo_dir, "target")
        git_target_path = os.path.relpath(target_path, self.local_repo_dir).replace(os.sep, '/')
        if os.path.exists(target_path):
            print(f"[GIT] EXCLUDING TARGET DIRECTORY FROM GIT: {git_target_path}")
            
            try:
                # Check if target directory has tracked files
                tracked_files_list = repo.git.ls_files(git_target_path)
                if tracked_files_list:
                    print(f"[GIT] Target directory has {len(tracked_files_list.splitlines())} tracked files - removing from Git index")
                    
                    # Remove all tracked files in target directory from Git index (but keep files locally)
                    for line in tracked_files_list.splitlines():
                        if line.strip():
                            try:
                                repo.git.rm("--cached", "-r", line.strip())
                                print(f"[GIT] Removed from Git index: {line.strip()}")
                            except git.GitCommandError as e:
                                print(f"[GIT] Could not remove {line.strip()} from index: {e}")
                    
                    # Remove the target directory itself from Git index
                    try:
                        repo.git.rm("-r", "--cached", git_target_path)
                        print(f"[GIT] Removed target directory from Git index: {git_target_path}")
                    except git.GitCommandError as e:
                        print(f"[GIT] Could not remove target directory from index: {e}")
                else:
                    print(f"[GIT] Target directory not tracked by Git (already excluded)")
            except git.GitCommandError:
                print(f"[GIT] Target directory not tracked by Git (already excluded)")
            
            # IMPORTANT: DO NOT delete the target directory - keep it for the application to run
            print(f"[GIT] Target directory preserved locally: {target_path}")
        else:
            print(f"[GIT] Target directory does not exist: {git_target_path}")
        # Handle 'app.py'
        app_py_path = os.path.join(self.local_repo_dir, "app.py")
        git_app_py_path = os.path.relpath(app_py_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files_list = repo.git.ls_files(git_app_py_path)
            if tracked_files_list:
                print(f"[GIT] Removing 'app.py' from index: {git_app_py_path}")
                repo.git.rm("--cached", git_app_py_path)
        except git.GitCommandError:
            pass
        # Handle 'requirements.txt'
        reqs_path = os.path.join(self.local_repo_dir, "requirements.txt")
        git_reqs_path = os.path.relpath(reqs_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files_list = repo.git.ls_files(git_reqs_path)
            if tracked_files_list:
                print(f"[GIT] Removing 'requirements.txt' from index: {git_reqs_path}")
                repo.git.rm("--cached", git_reqs_path)
        except git.GitCommandError:
            pass

        # Check if there are any changes to commit
        if not repo.index.diff('HEAD') and not repo.untracked_files and not deleted_files:
            print("[GIT] No changes to commit.")
            return

        # If we have deleted files but they're not showing in the index, try a more aggressive approach
        if deleted_files:
            print("[GIT] Attempting aggressive Git cleanup for deleted files...")
            try:
                # Instead of git add -A, selectively add only the files we want
                # First, reset the index to clean state
                repo.git.reset('HEAD')
                print("[GIT] Reset index to clean state")
                
                # Add only the files we want (excluding .bak, target, etc.)
                for root, dirs, files in os.walk(self.local_repo_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, self.local_repo_dir).replace(os.sep, '/')
                        
                        # Skip files we don't want to commit
                        if (rel_path.endswith('.bak') or 
                            rel_path.endswith('.backup') or 
                            rel_path.endswith('.old') or
                            rel_path.startswith('target/') or
                            rel_path == 'app.py' or
                            rel_path == 'requirements.txt' or
                            '.idea/' in rel_path or
                            '.vscode/' in rel_path or
                            rel_path.endswith('.iml')):
                            continue
                        
                        # Add only source code and config files
                        if (rel_path.endswith(('.java', '.xml', '.yml', '.yaml', '.properties', '.md', '.txt')) or
                            rel_path.startswith('src/') or
                            rel_path.startswith('pom.xml')):
                            try:
                                repo.index.add([rel_path])
                                print(f"[GIT] Added to index: {rel_path}")
                            except Exception as e:
                                print(f"[GIT] Could not add {rel_path}: {e}")
                
                # Now handle deletions specifically
                for deleted_file in deleted_files:
                    try:
                        repo.git.rm("--cached", deleted_file)
                        print(f"[GIT] Removed deleted file from index: {deleted_file}")
                    except git.GitCommandError as e:
                        print(f"[GIT] Could not remove {deleted_file}: {e}")
                
                print("[GIT] Selective staging completed")
                
                # Check status again
                staged_changes = repo.index.diff('HEAD')
                if staged_changes:
                    print(f"[GIT] Now have {len(staged_changes)} staged changes")
                else:
                    print("[GIT] Still no staged changes after selective staging")
            except Exception as e:
                print(f"[GIT] Aggressive cleanup failed: {e}")

        print(f"[GIT] Committing changes with message: {commit_message}")
        
        # Debug: Show what's staged for commit
        print("[GIT] Debug: Staged changes:")
        try:
            staged = repo.git.diff('--cached', '--name-status')
            if staged:
                print(staged)
            else:
                print("No staged changes")
        except Exception as e:
            print(f"Could not show staged changes: {e}")
        
        repo.index.commit(commit_message)
        print(f"[GIT] Pushing branch: {branch_name}")
        repo.remotes.origin.push(branch_name)
        print(f"✅ Code committed and pushed to branch: {branch_name}")

    def create_merge_request(self, source_branch, target_branch, mr_title, mr_description):
        try:
            mr = self.project.mergerequests.create({
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': mr_title,
                'description': mr_description,
                'remove_source_branch': True
            })
            print(f"Merge Request created successfully! URL: {mr.web_url}")
            return mr.web_url
        except GitlabError as e:
            print(f"Error creating Merge Request: {e}")
            return None
