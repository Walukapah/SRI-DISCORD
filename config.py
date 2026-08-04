import os
import json
import hashlib
from pathlib import Path
from github_backup import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO

BASE_DIR = Path(__file__).parent
CONFIGS_DIR = BASE_DIR / "configs"
CONFIGS_DIR.mkdir(exist_ok=True)

# ⚠️ MAIN_BOT_TOKEN MUST be set via environment variable!
BASE_CONFIG = {
    "MAIN_BOT_TOKEN": os.getenv("MAIN_BOT_TOKEN", ""),
    "PREFIX": os.getenv("PREFIX", "."),
    "BOT_NAME": os.getenv("BOT_NAME", "SRI-DISCORD-BOT"),
    "OWNER_ID": os.getenv("OWNER_ID", ""),
    "MODE": os.getenv("MODE", "public"),
    "VERSION": "1.0.0",
    "AUTO_STATUS": os.getenv("AUTO_STATUS", "true"),
}

class ConfigManager:
    def __init__(self):
        self.configs = {}
        self.github = None
        self.repo = None
        
        if GITHUB_TOKEN:
            try:
                from github import Github
                self.github = Github(GITHUB_TOKEN)
                self.repo = self.github.get_repo(f"{GITHUB_OWNER}/{GITHUB_REPO}")
                print("[CONFIG] GitHub backup enabled")
            except Exception as e:
                print(f"[CONFIG] GitHub init failed: {e}")
    
    def get_bot_id(self, token: str) -> str:
        return hashlib.md5(token.encode()).hexdigest()[:12]
    
    def get_config_path(self, bot_id: str) -> Path:
        return CONFIGS_DIR / f"config_{bot_id}.json"
    
    def get_github_path(self, bot_id: str) -> str:
        return f"configs/config_{bot_id}.json"
    
    def create_config(self, token: str, owner_id: str = None, extra: dict = None) -> dict:
        bot_id = self.get_bot_id(token)
        
        config = {
            "BOT_ID": bot_id,
            "TOKEN": token,
            "OWNER_ID": owner_id or "",
            "PREFIX": BASE_CONFIG["PREFIX"],
            "BOT_NAME": f"Sub-Bot-{bot_id[:6]}",
            "MODE": "public",
            "CONNECTED_AT": str(__import__('datetime').datetime.now()),
            "IS_SUB_BOT": True,
        }
        
        if extra:
            config.update(extra)
        
        self._save_local(bot_id, config)
        self._backup_to_github(bot_id, config)
        self.configs[bot_id] = config
        
        return config
    
    def get_config(self, bot_id: str = None, token: str = None) -> dict:
        if token and not bot_id:
            bot_id = self.get_bot_id(token)
        
        if not bot_id:
            return BASE_CONFIG.copy()
        
        if bot_id in self.configs:
            return self.configs[bot_id]
        
        local = self._load_local(bot_id)
        if local:
            self.configs[bot_id] = local
            return local
        
        github = self._load_from_github(bot_id)
        if github:
            self._save_local(bot_id, github)
            self.configs[bot_id] = github
            return github
        
        return None
    
    def update_config(self, bot_id: str, updates: dict) -> dict:
        config = self.get_config(bot_id=bot_id) or {}
        config.update(updates)
        self._save_local(bot_id, config)
        self._backup_to_github(bot_id, config)
        self.configs[bot_id] = config
        return config
    
    def delete_config(self, bot_id: str):
        path = self.get_config_path(bot_id)
        if path.exists():
            path.unlink()
        
        if bot_id in self.configs:
            del self.configs[bot_id]
        
        self._delete_from_github(bot_id)
    
    def list_configs(self) -> list:
        configs = []
        for f in CONFIGS_DIR.glob("config_*.json"):
            try:
                with open(f, "r") as fp:
                    cfg = json.load(fp)
                    safe = {k: v for k, v in cfg.items() if k != "TOKEN"}
                    safe["BOT_ID"] = cfg.get("BOT_ID", "")
                    configs.append(safe)
            except:
                pass
        return configs
    
    def _save_local(self, bot_id: str, config: dict):
        path = self.get_config_path(bot_id)
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
    
    def _load_local(self, bot_id: str) -> dict:
        path = self.get_config_path(bot_id)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None
    
    def _backup_to_github(self, bot_id: str, config: dict):
        if not self.repo:
            return
        
        try:
            path = self.get_github_path(bot_id)
            content = json.dumps(config, indent=2)
            content_b64 = __import__('base64').b64encode(content.encode()).decode()
            
            sha = None
            try:
                file = self.repo.get_contents(path)
                sha = file.sha
            except:
                pass
            
            if sha:
                self.repo.update_file(path, f"Update config for bot {bot_id}", content, sha)
            else:
                self.repo.create_file(path, f"Create config for bot {bot_id}", content)
            print(f"[GITHUB] Config backed up for bot {bot_id}")
        except Exception as e:
            print(f"[GITHUB] Backup failed: {e}")
    
    def _load_from_github(self, bot_id: str) -> dict:
        if not self.repo:
            return None
        
        try:
            path = self.get_github_path(bot_id)
            file = self.repo.get_contents(path)
            content = __import__('base64').b64decode(file.content).decode()
            return json.loads(content)
        except Exception as e:
            print(f"[GITHUB] Load failed: {e}")
            return None
    
    def _delete_from_github(self, bot_id: str):
        if not self.repo:
            return
        
        try:
            path = self.get_github_path(bot_id)
            file = self.repo.get_contents(path)
            self.repo.delete_file(path, f"Delete config for bot {bot_id}", file.sha)
            print(f"[GITHUB] Config deleted for bot {bot_id}")
        except Exception as e:
            print(f"[GITHUB] Delete failed: {e}")

config_manager = ConfigManager()
