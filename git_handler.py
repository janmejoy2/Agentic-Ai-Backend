import os
import git
import gitlab
from datetime import datetime
from gitlab.exceptions import GitlabError

class AgenticGitHandler:
    def __init__(self, gitlab_url, repo_path, private_token, default_branch, local_repo_dir):
        self.gitlab_url = gitlab_url
        self.repo_path = repo_path
        self.private_token = private_token
        self.default_branch = default_branch
        self.local_repo_dir = local_repo_dir
        self.project = gitlab.Gitlab(gitlab_url, private_token=private_token).projects.get(repo_path)

    def clone_or_pull_repo(self):
        print(f"Cloning/pulling repository: {self.repo_path} into {self.local_repo_dir}")
        if os.path.exists(self.local_repo_dir):
            repo = git.Repo(self.local_repo_dir)
            try:
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

        # Exclude app.py, requirements.txt, and target directory
        repo.git.add(".")
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
