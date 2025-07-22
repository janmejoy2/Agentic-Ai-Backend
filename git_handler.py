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
        # Try to find and kill any Java process running from this repo's target directory
        try:
            # List all Java processes (requires JDK's jps tool)
            result = subprocess.run(['jps', '-l'], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if 'jar' in line or 'war' in line:
                    pid, name = line.split(maxsplit=1)
                    # If the process is running from our target dir or matches our JAR/WAR, kill it
                    if 'target' in name or local_repo_dir in name:
                        print(f"Killing Java process {pid} ({name})")
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                        except Exception as e:
                            print(f"Failed to kill process {pid}: {e}")
        except Exception as e:
            print(f"Could not check or kill Java processes: {e}")

        # Now try to delete the files
        for fname in ['deployment.log', 'employee-servlet-api-0.0.1-SNAPSHOT.jar']:
            fpath = os.path.join(target_dir, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    print(f"Deleted {fpath}")
                except Exception as e:
                    print(f"Failed to delete {fpath}: {e}")

    def clone_or_pull_repo(self):
        print(f"Cloning/pulling repository: {self.repo_path} into {self.local_repo_dir}")
        if os.path.exists(self.local_repo_dir):
            repo = git.Repo(self.local_repo_dir)
            try:
                # Stop any running Spring server and delete locked files before git operations
                self.stop_spring_server_and_cleanup(self.local_repo_dir)
                # Clean untracked files and reset tracked files before checkout
                repo.git.reset('--hard')
                repo.git.clean('-fd')
                # Force remove problematic deployment.log from index and disk if it exists
                log_path = os.path.join(self.local_repo_dir, 'target', 'deployment.log')
                git_log_path = os.path.relpath(log_path, self.local_repo_dir).replace(os.sep, '/')
                if os.path.exists(log_path):
                    try:
                        # Remove from git index if staged
                        try:
                            repo.git.rm('-f', '--cached', git_log_path)
                        except Exception:
                            pass  # Ignore if not staged
                        os.remove(log_path)
                        print(f"Deleted problematic file: {log_path}")
                    except Exception as e:
                        print(f"Failed to delete {log_path}: {e}")
                repo.git.checkout(self.default_branch)
                if repo.active_branch.tracking_branch() is None:
                    repo.git.branch(f"--set-upstream-to=origin/{self.default_branch}", self.default_branch)
                repo.remotes.origin.pull()
                print(f"Repository updated on branch '{self.default_branch}'.")
            except Exception as e:
                print(f"Error during pull: {e}")
                raise e
        else:
            repo_url = f"https://oauth2:{self.private_token}@{self.gitlab_url.split('//')[1]}/{self.repo_path}.git"
            repo = git.Repo.clone_from(repo_url, self.local_repo_dir, branch=self.default_branch)
            print(f"Repository cloned on branch '{self.default_branch}'.")
        return repo

    def apply_and_commit_changes(self, repo, branch_name, commit_message):
        try:
            repo.git.checkout('HEAD', b=branch_name)
        except git.GitCommandError as e:
            if "already exists" in str(e):
                repo.git.checkout(branch_name)
            else:
                raise e

        # Exclude app.py, requirements.txt, target directory, and .bak files
        repo.git.add(".")
        # Remove .bak files from git index if any are staged
        for root, dirs, files in os.walk(self.local_repo_dir):
            for file in files:
                if file.endswith('.bak'):
                    bak_path = os.path.relpath(os.path.join(root, file), self.local_repo_dir).replace(os.sep, '/')
                    try:
                        tracked_files = repo.git.ls_files(bak_path)
                        if tracked_files:
                            repo.git.rm("--cached", bak_path)
                    except git.GitCommandError:
                        pass
        # Handle 'target' directory
        target_path = os.path.join(self.local_repo_dir, "target")
        git_target_path = os.path.relpath(target_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_target_path)
            if tracked_files:
                repo.git.rm("-r", "--cached", git_target_path)
        except git.GitCommandError:
            pass  # Ignore if not tracked
        # Handle 'app.py'
        app_py_path = os.path.join(self.local_repo_dir, "app.py")
        git_app_py_path = os.path.relpath(app_py_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_app_py_path)
            if tracked_files:
                repo.git.rm("--cached", git_app_py_path)
        except git.GitCommandError:
            pass
        # Handle 'requirements.txt'
        reqs_path = os.path.join(self.local_repo_dir, "requirements.txt")
        git_reqs_path = os.path.relpath(reqs_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_reqs_path)
            if tracked_files:
                repo.git.rm("--cached", git_reqs_path)
        except git.GitCommandError:
            pass

        repo.index.commit(commit_message)
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
