from dataclasses import dataclass
from typing import Dict, Optional, Tuple

@dataclass(frozen=True)
class User:
    username: str
    role: str   # "trainee" | "trainer"

def _make_accounts() -> Dict[str, Tuple[str, str]]:
    """
    returns: username -> (password, role)
    v1: 内置账号，不用服务器
    """
    accounts: Dict[str, Tuple[str, str]] = {}

    # 20 trainees
    for i in range(1, 21):
        u = f"training{i:02d}"
        p = "train123"
        accounts[u] = (p, "trainee")

    # 10 trainers
    for i in range(1, 11):
        u = f"trainer{i:02d}"
        p = "teach123"
        accounts[u] = (p, "trainer")

    return accounts

ACCOUNTS = _make_accounts()

def authenticate(username: str, password: str) -> Optional[User]:
    username = (username or "").strip()
    password = password or ""
    rec = ACCOUNTS.get(username)
    if not rec:
        return None
    pw, role = rec
    if password != pw:
        return None
    return User(username=username, role=role)
