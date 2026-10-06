import json, os, time, re, math
from collections import defaultdict
import aiohttp

ESC    = "\x1b"
RESET  = f"{ESC}[0m"
GREY   = f"{ESC}[2;37m"
WHITE  = f"{ESC}[1;37m"
CYAN   = f"{ESC}[36m"
GREEN  = f"{ESC}[32m"
RED    = f"{ESC}[31m"
YELLOW = f"{ESC}[33m"
BLUE   = f"{ESC}[34m"
DIM    = f"{ESC}[2m"
DARK   = f"{ESC}[30m"
BOLD   = f"{ESC}[1m"
CYAN2  = f"{ESC}[0;36m"
WHITE2 = f"{ESC}[0;37m"
BLUE2  = f"{ESC}[0;34m"
BRAND  = f"{ESC}[0;35m{ESC}[1m{ESC}[4m"

BOT     = None    # set in selfbot.py on_ready
TOKEN   = ""
PREFIX  = "."
STEALTH_DELETE = True
STEALTH_DELETE_SECONDS = 5
DISCORD_MSG_LIMIT = 2000
VERSION = "3.0.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def load_config() -> dict:
    try:
        if os.path.exists("config.json"):
            with open("config.json", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(cfg: dict) -> None:
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[state] save_config: {e}")

_aliases:       dict = {}
_cooldowns:     dict = {}
_cooldown_last: dict = {}
_cmd_disabled:  set  = set()
_global_cooldown: float = 0.0
_server_prefixes: dict = {}

_user_blacklist: set = set()
_user_whitelist: set = set()
_role_restrict:  set  = set()
_perm_allow:     dict = {}
_perm_block:     set  = set()
_perm_channel:   dict = {}
_perm_server:    dict = {}
_admins:         set  = set()
_devs:           set  = set()

afk = {
    "enabled": False,
    "message": "",
    "expires_at": 0,
    "since": 0,
    "emergency": False,
    "dm_only": False,
    "cooldown": 30,
    "blacklist": set(),
    "whitelist": set(),
    "custom_replies": {},
    "per_server": {},
    "ping_counter": {},
    "last_reply": {},
}

filters = {
    "spam":        {"enabled": False, "threshold": 5, "window": 5, "history": {}},
    "duplicate":   {"enabled": False, "window": 30, "history": {}},
    "link":        {"enabled": False, "whitelist": set()},
    "invite":      {"enabled": False},
    "attachment":  {"enabled": False},
    "nsfw":        {"enabled": False, "keywords": set()},
    "mention_spam":{"enabled": False, "threshold": 5},
    "mass_ping":   {"enabled": False},
    "scam":        {"enabled": False},
    "bot":         {"enabled": False},
    "webhook":     {"enabled": False},
    "auto_purge":  {"enabled": False, "keep": 50},
    "log_channel": None, "actions_log": [],
}

loggers = {k: {"enabled": False, "channel": None}
           for k in ("message","deleted","edited","reaction",
                     "mention","dm","joins","leaves")}

SNIPER_ENABLED = True
_snipe_cache:     dict = {}
_editsnipe_cache: dict = {}
_vsniper_list:    list = []
_vsniper_task = None
_nitrosniper_enabled = True
_giveaway_enabled    = False

_current_platform = "desktop"

AUTO_RESPONSES:      dict = {}
_autoreact_users:    dict = {}
_multireact_users:   dict = {}
_mimic_dict:         dict = {}
_tracked_users:      set  = set()
_tracking:           dict = {}
_autoaddback:        bool = False

ar_rules:     list = []
ar_variables: dict = {}

_triggers = {"message": [], "reaction": [], "voice": [], "member": []}
_trigger_fired_counts: dict = {}

nickname = {
    "enabled": False, "pattern": "{user}",
    "interval": 300, "history": {},
}

meta = {
    "debug": False, "dev_mode": False,
    "status_watch": {"enabled": False, "interval": 300, "last": 0},
    "webhook": None, "github_repo": None,
    "gh_notify_ch": None, "github_last": None,
}

_scheduler:     list = []
_managed_tasks: dict = {}
_TASK_STORE:    dict = {}
_TRIGGER_STORE: dict = {}

_db      = None
_db_path = "database.db"

_pending_interactions: list = []
_buttons_enabled = False
_modals_enabled  = False
_spam_tasks:      dict = {}
_proxy           = None
_plugins:         dict = {}
_sessions:        list = []
_session_idx     = 0
_cache_auto      = False
_latency_history: list = []
_session_events:  list = []
_rate_limit_events: list = []
_rate_limit:      dict = {}
_cmd_queue:       list = []
_auto_reconnect  = True
_auto_restart    = False
_reconnect_count = 0
_protect_enabled = False
_protect_log_ch  = 0
_serverguard_enabled  = False
_serverguard_keywords: set = {
    "child porn","cp server","csam","loli porn","shota porn",
    "gore server","snuff","animal abuse","zoophilia server",
    "drug market","hitman","terrorism","mass shooter",
    "ddos server","rat server","malware server",
}
_serverguard_log_ch: int = 0
LOGGER_ENABLED = False
LOG_FILE = "wilt.log"
LASTFM_BASE = "http://ws.audioscrobbler.com/2.0/"
HOUSE_IDS   = {}
HOUSE_NAMES = {}
_agc_state = {
    "enabled": False, "block": False, "leave_msg": "",
    "gc_name": "", "gc_icon_url": None, "webhook_url": None,
}
_agc_whitelist: set = set()
_automod = {"enabled": False, "words": [], "action": "delete", "log_ch": None}
_raidmode = {"enabled": False, "threshold": 10}
_quarantine = {"enabled": False, "role_id": None, "age_days": 7}
_ticket_cfg = {"category_id": None}
_verify_cfg = {"role_id": None}
_speak_lang = None
neko_gif = None
HOSTED_TOKENS: list = []
_host_sessions: list = []
_hosted_clients: list = []
_live_prefix: list = ["."]


def _clip(text: str, limit: int = None) -> str:
    limit = limit or DISCORD_MSG_LIMIT
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)] + "\n…(trimmed)"

def _ansi_block(lines) -> str:
    parts = []
    for line in lines:
        parts.append("" if not line.strip() else line)
    body = chr(10).join(parts).strip()
    return _clip("```ansi\n" + body + "\n```")

def ui_box(title: str, rows, footer: str = "") -> str:
    lines = [f"  {WHITE}{title}{RESET}"] + list(rows)
    if footer: lines += ["", f"  {DIM}{footer}{RESET}"]
    return _ansi_block(lines)

def ui_ok(msg):   return _ansi_block([f"  {GREEN}✓{RESET}  {msg}"])
def ui_err(msg):  return _ansi_block([f"  {RED}✗{RESET}  {msg}"])
def ui_info(msg): return _ansi_block([f"  {CYAN}•{RESET}  {msg}"])
def ui_warn(msg): return _ansi_block([f"  {YELLOW}!{RESET}  {msg}"])

def ui_progress(label: str, pct: int) -> str:
    filled = int(max(0, min(pct, 100)) / 10)
    bar    = f"{GREEN}{'█' * filled}{GREY}{'░' * (10 - filled)}{RESET}"
    return f"  {bar} {WHITE}{pct}%{RESET}  {DIM}{label}{RESET}"

def _paginate(title: str, subtitle: str, rows: list, page: int = 1) -> str:
    PAGE  = 8
    total = max(1, math.ceil(len(rows) / PAGE))
    page  = max(1, min(page, total))
    chunk = rows[(page-1)*PAGE : page*PAGE]
    lines = [f"  {WHITE}> {title}{RESET}  {DIM}{subtitle}{RESET}", ""] + chunk + [
        "", f"  {DIM}page {page}/{total}{RESET}",
    ]
    return _ansi_block(lines)

def _get_session():
    return None  # aiohttp sessions now managed per-cog or via bot._session

def log_msg(msg: str):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception: pass

OWNER_ID: int           = 0
def access_save():
    """Persist OWNER_ID / admins / devs into config.json."""
    try:
        cfg = load_config()
        cfg["owner_id"] = OWNER_ID
        cfg["admins"] = list(_admins)
        cfg["devs"] = list(_devs)
        save_config(cfg)
    except Exception as e:
        print(f"[state] access_save: {e}")


_channel_blacklist: set  = set()
_server_blacklist:  set  = set()
_user_notes:        dict = {}
personal_blocklist: set  = set()
personal_ignore:    set  = set()
profile_history:    dict = {}

_ping_tracking: dict = {}
_ping_log:      list = []

_notify_watch: dict = {}

_dev_mode:     bool = False
_error_log:    list = []
_github_watch: dict = {}

_vsniper_enabled: bool = True
_autoreconnect:   bool = True   # alias for _auto_reconnect
_autorestart:     bool = False  # alias for _auto_restart

_serverguard_user_whitelist: set = set()
_user_blacklist2: set = set()

def get(key, default=None):
    import cogs.state as _s
    return getattr(_s, key, default)

try:
    _ac = load_config()
    if _ac.get("owner_id"):
        OWNER_ID = int(_ac["owner_id"])
    if _ac.get("admins"):
        _admins.update(int(x) for x in _ac["admins"])
    if _ac.get("devs"):
        _devs.update(int(x) for x in _ac["devs"])
except Exception:
    pass

def save_afk() -> None:
    try:
        cfg = load_config()
        a = afk
        cfg["afk"] = {
            "enabled": bool(a.get("enabled")),
            "message": a.get("message") or "",
            "emergency": bool(a.get("emergency")),
            "dm_only": bool(a.get("dm_only")),
            "cooldown": int(a.get("cooldown") or 30),
            "expires_at": float(a.get("expires_at") or 0),
            "since": float(a.get("since") or 0),
            "blacklist": list(a.get("blacklist") or []),
            "whitelist": list(a.get("whitelist") or []),
            "custom_replies": dict(a.get("custom_replies") or {}),
            "per_server": dict(a.get("per_server") or {}),
        }
        save_config(cfg)
    except Exception as e:
        print(f"[state] save_afk: {e}")

def load_afk() -> None:
    try:
        cfg = load_config()
        data = cfg.get("afk") or {}
        if not data:
            return
        afk["enabled"] = bool(data.get("enabled"))
        afk["message"] = data.get("message") or ""
        afk["emergency"] = bool(data.get("emergency"))
        afk["dm_only"] = bool(data.get("dm_only"))
        afk["cooldown"] = int(data.get("cooldown") or 30)
        afk["expires_at"] = float(data.get("expires_at") or 0)
        afk["since"] = float(data.get("since") or 0)
        afk["blacklist"] = set(data.get("blacklist") or [])
        afk["whitelist"] = set(data.get("whitelist") or [])
        afk["custom_replies"] = dict(data.get("custom_replies") or {})
        afk["per_server"] = dict(data.get("per_server") or {})
        afk["ping_counter"] = {}
        afk["last_reply"] = {}
    except Exception as e:
        print(f"[state] load_afk: {e}")

