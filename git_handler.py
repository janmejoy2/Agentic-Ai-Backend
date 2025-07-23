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

        # Only add and commit files that have actually changed
        changed_files = [item.a_path for item in repo.index.diff(None)] + repo.untracked_files
        # Only include files that exist on disk
        existing_files = [f for f in changed_files if os.path.exists(os.path.join(self.local_repo_dir, f))]
        missing_files = [f for f in changed_files if not os.path.exists(os.path.join(self.local_repo_dir, f))]
        if missing_files:
            print(f"[GIT] Skipping missing files (not found on disk): {missing_files}")
        if not existing_files:
            print("[GIT] No changes to commit.")
            return
        print(f"[GIT] Adding changed files to index: {existing_files}")
        repo.index.add(existing_files)

        # Remove .bak files from git index if any are staged
        for root, dirs, files in os.walk(self.local_repo_dir):
            for file in files:
                if file.endswith('.bak'):
                    bak_path = os.path.relpath(os.path.join(root, file), self.local_repo_dir).replace(os.sep, '/')
                    try:
                        tracked_files = repo.git.ls_files(bak_path)
                        if tracked_files:
                            print(f"[GIT] Removing .bak file from index: {bak_path}")
                            repo.git.rm("--cached", bak_path)
                    except git.GitCommandError:
                        pass
        # Handle 'target' directory
        target_path = os.path.join(self.local_repo_dir, "target")
        git_target_path = os.path.relpath(target_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_target_path)
            if tracked_files:
                print(f"[GIT] Removing 'target' directory from index: {git_target_path}")
                repo.git.rm("-r", "--cached", git_target_path)
        except git.GitCommandError:
            pass  # Ignore if not tracked
        # Handle 'app.py'
        app_py_path = os.path.join(self.local_repo_dir, "app.py")
        git_app_py_path = os.path.relpath(app_py_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_app_py_path)
            if tracked_files:
                print(f"[GIT] Removing 'app.py' from index: {git_app_py_path}")
                repo.git.rm("--cached", git_app_py_path)
        except git.GitCommandError:
            pass
        # Handle 'requirements.txt'
        reqs_path = os.path.join(self.local_repo_dir, "requirements.txt")
        git_reqs_path = os.path.relpath(reqs_path, self.local_repo_dir).replace(os.sep, '/')
        try:
            tracked_files = repo.git.ls_files(git_reqs_path)
            if tracked_files:
                print(f"[GIT] Removing 'requirements.txt' from index: {git_reqs_path}")
                repo.git.rm("--cached", git_reqs_path)
        except git.GitCommandError:
            pass

        print(f"[GIT] Committing changes with message: {commit_message}")
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
