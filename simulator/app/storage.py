import json
from pathlib import Path
from datetime import datetime
from app.config import DATA_DIR_NAME

def app_root_dir() -> Path:
    # 运行目录（exe 同级）
    return Path.cwd()

def data_root() -> Path:
    p = app_root_dir() / DATA_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def user_dir(username: str) -> Path:
    p = data_root() / username
    p.mkdir(parents=True, exist_ok=True)
    (p / "training_logs").mkdir(exist_ok=True)
    (p / "question_results").mkdir(exist_ok=True)
    (p / "reports").mkdir(exist_ok=True)
    (p / "media_cache").mkdir(exist_ok=True)
    return p

def write_profile_if_missing(username: str, role: str) -> None:
    p = user_dir(username) / "profile.json"
    if p.exists():
        return
    payload = {
        "username": username,
        "role": role,
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
