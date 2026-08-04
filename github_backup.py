import os
import json
import base64
from github import Github

# ============================================
# GITHUB CONFIG - CHANGE ONLY HERE
# ============================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_REPO_OWNER", "Walukapah")
GITHUB_REPO = os.getenv("GITHUB_REPO_NAME", "SRI-DISCORD-BOT")

class GitHubBackup:
    def __init__(self):
        self.github = None
        self.repo = None
        if GITHUB_TOKEN:
            try:
                self.github = Github(GITHUB_TOKEN)
                self.repo = self.github.get_repo(f"{GITHUB_OWNER}/{GITHUB_REPO}")
                print("[GITHUB] Backup manager ready")
            except Exception as e:
                print(f"[GITHUB] Init error: {e}")
    
    def save_file(self, path: str, content: dict or str, message: str = None):
        if not self.repo:
            return False
        
        try:
            if isinstance(content, dict):
                content = json.dumps(content, indent=2)
            
            content_b64 = base64.b64encode(content.encode()).decode()
            full_path = f"sessions/{path}"
            
            sha = None
            try:
                file = self.repo.get_contents(full_path)
                sha = file.sha
            except:
                pass
            
            msg = message or f"Update {path}"
            
            if sha:
                self.repo.update_file(full_path, msg, content, sha)
            else:
                self.repo.create_file(full_path, msg, content)
            
            return True
        except Exception as e:
            print(f"[GITHUB] Save error: {e}")
            return False
    
    def load_file(self, path: str):
        if not self.repo:
            return None
        
        try:
            full_path = f"sessions/{path}"
            file = self.repo.get_contents(full_path)
            content = base64.b64decode(file.content).decode()
            try:
                return json.loads(content)
            except:
                return content
        except Exception as e:
            print(f"[GITHUB] Load error: {e}")
            return None
    
    def delete_file(self, path: str):
        if not self.repo:
            return False
        
        try:
            full_path = f"sessions/{path}"
            file = self.repo.get_contents(full_path)
            self.repo.delete_file(full_path, f"Delete {path}", file.sha)
            return True
        except Exception as e:
            print(f"[GITHUB] Delete error: {e}")
            return False

backup = GitHubBackup()
