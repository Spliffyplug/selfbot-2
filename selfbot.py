import os, sys, json, math, time, asyncio, signal
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

def _load_cfg():
    try:
        with open("config.json", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def _save_cfg(cfg):
    try:
        with open("config.json", "w", encoding="utf-8") as f: json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[cfg] save failed: {e}")

_cfg    = _load_cfg()
TOKEN   = os.environ.get("TOKEN") or _cfg.get("token", "")
VERSION = "3.0.1"

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

def _get_prefix(bot, message):
    from cogs import state as S
    gid = str(getattr(message.guild, "id", "")) if message.guild else ""
    if gid and gid in S._server_prefixes:
        return S._server_prefixes[gid]
    return S.PREFIX

class WiltBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix = _get_prefix,
            self_bot       = True,
            help_command   = None,
            chunk_guilds_at_startup = False,
        )
        self._wilt_delete_ids = set()

    async def setup_hook(self):
        """Load all cogs before connecting."""
        COGS = [
            "cogs.general",   "cogs.settings",  "cogs.information",
            "cogs.server",    "cogs.afk",        "cogs.auto",
            "cogs.autoresponder","cogs.automod",  "cogs.backup",
            "cogs.bumper",    "cogs.db",          "cogs.developer",
            "cogs.downloads", "cogs.filters",     "cogs.fun",
            "cogs.gc",        "cogs.guards",       "cogs.host",
            "cogs.interactions","cogs.lastfm",    "cogs.loggers",
            "cogs.mass",      "cogs.meta",         "cogs.monitor",
            "cogs.multispoof","cogs.nickname",    "cogs.nuke",
            "cogs.perms",     "cogs.pingtrack",   "cogs.profile",
            "cogs.profile_ext","cogs.protect",    "cogs.quests",
            "cogs.reminders", "cogs.resilience",  "cogs.rolemgmt",
            "cogs.rpc", "cogs.scheduler",
            "cogs.scrape",    "cogs.search",       "cogs.sniper",
            "cogs.social",    "cogs.spoofer",      "cogs.status",
            "cogs.tasks",     "cogs.tools",        "cogs.tracking",
            "cogs.triggers",  "cogs.utility",      "cogs.voice",
            "cogs.webhooks",  "cogs.ai",           "cogs.agc",
        ]
        ok = fail = 0
        for cog in COGS:
            try:
                await self.load_extension(cog)
                ok += 1
            except Exception as e:
                print(f"[boot] SKIP {cog}: {e}")
                fail += 1
        print(f"[boot] cogs: {ok} loaded, {fail} failed")

    async def on_ready(self):
        from cogs import state as S
        S.BOT    = self
        S.TOKEN  = self.http.token or TOKEN
        S.PREFIX = _cfg.get("prefix", ".")
        S.STEALTH_DELETE = bool(_cfg.get("stealth_delete", True))
        S.STEALTH_DELETE_SECONDS = float(_cfg.get("stealth_delete_seconds", 5))
        S._live_prefix[0] = S.PREFIX
        try:
            S.load_afk()
        except Exception as e:
            print(f"[wilt] load_afk: {e}")
        print(f"[wilt] v{VERSION} | {self.user} | {len(self.guilds)} guilds")

    def _schedule_stealth_delete(self, msg, delay: float | None = None):
        """Schedule deletion without setting attrs on Message (discord.py-self forbids it)."""
        if not msg:
            return
        mid = getattr(msg, "id", None)
        if mid is None:
            return
        ids = getattr(self, "_wilt_delete_ids", None)
        if ids is None:
            self._wilt_delete_ids = set()
            ids = self._wilt_delete_ids
        if mid in ids:
            return
        ids.add(mid)
        if delay is None:
            from cogs import state as S
            delay = float(getattr(S, "STEALTH_DELETE_SECONDS", 5) or 5)

        async def _del():
            await asyncio.sleep(delay)
            try:
                await msg.delete()
            except Exception:
                pass
            finally:
                try:
                    self._wilt_delete_ids.discard(mid)
                except Exception:
                    pass
        asyncio.create_task(_del())

    async def on_command_completion(self, ctx):
        """Schedule delete of the command message after stealth delay."""
        from cogs import state as S
        try:
            if not getattr(S, "STEALTH_DELETE", True):
                return
            if getattr(ctx, "_wilt_skip_delete", False):
                return
            self._schedule_stealth_delete(ctx.message)
        except Exception as e:
            print(f"[stealth-delete] {e}")

    async def on_command_error(self, ctx, error):
        from cogs import state as S
        try:
            if getattr(S, "STEALTH_DELETE", True):
                self._schedule_stealth_delete(getattr(ctx, "message", None))
        except Exception:
            pass

        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandOnCooldown):
            try:
                return await ctx.message.edit(
                    content=f"```ansi\n  \x1b[31m✗\x1b[0m  cooldown: {error.retry_after:.1f}s\n```")
            except Exception:
                return
        if isinstance(error, commands.MissingRequiredArgument):
            try:
                return await ctx.message.edit(
                    content=f"```ansi\n  \x1b[31m✗\x1b[0m  missing argument: {error.param}\n```")
            except Exception:
                return
        if isinstance(error, commands.BadArgument):
            try:
                return await ctx.message.edit(
                    content=f"```ansi\n  \x1b[31m✗\x1b[0m  bad argument: {error}\n```")
            except Exception:
                return
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.message.edit(
                    content=f"```ansi\n  \x1b[31m✗\x1b[0m  guild only\n```")
            except Exception:
                return
        err = getattr(error, "original", error)
        print(f"[error] {ctx.command}: {type(err).__name__}: {err}")

    async def _dispatch_cog_event(self, event_name: str, *args, **kwargs):
        for cog_name, cog in list(self.cogs.items()):
            try:
                listeners = getattr(cog, "__cog_listeners__", None) or []
                for ev, method_name in listeners:
                    if ev != event_name:
                        continue
                    meth = getattr(cog, method_name, None)
                    if not meth:
                        continue
                    try:
                        await meth(*args, **kwargs)
                    except Exception as e:
                        print(f"[listener {cog_name}.{method_name}] {e}")
            except Exception as e:
                print(f"[cog-dispatch {cog_name}] {e}")

    async def on_message(self, message):
        from cogs import state as S
        await self._dispatch_cog_event("on_message", message)

        if self.user and message.author.id == self.user.id:
            await self.process_commands(message)
            try:
                auto = self.get_cog("auto")
                if auto is not None:
                    await auto._handle_self_message(message)
            except Exception as e:
                print(f"[auto] self-hook: {e}")
            try:
                ctx = await self.get_context(message)
                if ctx.valid and ctx.command is not None and getattr(S, "STEALTH_DELETE", True):
                    self._schedule_stealth_delete(message)
            except Exception:
                pass

    async def on_message_delete(self, message):
        await self._dispatch_cog_event("on_message_delete", message)

    async def on_message_edit(self, before, after):
        await self._dispatch_cog_event("on_message_edit", before, after)

    async def on_member_join(self, member):
        await self._dispatch_cog_event("on_member_join", member)

    async def on_member_remove(self, member):
        await self._dispatch_cog_event("on_member_remove", member)

    async def on_guild_channel_delete(self, channel):
        await self._dispatch_cog_event("on_guild_channel_delete", channel)

    async def on_guild_update(self, before, after):
        await self._dispatch_cog_event("on_guild_update", before, after)

    async def on_group_join(self, channel, user):
        await self._dispatch_cog_event("on_group_join", channel, user)

    async def on_connect(self):
        await self._dispatch_cog_event("on_connect")

    async def on_disconnect(self):
        await self._dispatch_cog_event("on_disconnect")

    async def on_resumed(self):
        await self._dispatch_cog_event("on_resumed")

    async def on_rate_limit(self, *args, **kwargs):
        await self._dispatch_cog_event("on_rate_limit", *args, **kwargs)

    async def process_commands(self, message):
        if not self.user or message.author.id != self.user.id:
            return
        await super().process_commands(message)


bot = WiltBot()

CATEGORY_ORDER = [
    "general",  "quests",   "sniper",       "afk",          "rpc",
    "spoofer",  "status",   "social",       "profile",      "profile_ext",
    "auto",     "autoresponder", "filters", "loggers",
    "tracking", "triggers", "reminders",    "pingtrack",    "guards",
    "voice",    "server",   "rolemgmt",     "information",  "settings",
    "meta",     "developer","tools",        "fun",          "utility",
    "mass",     "nuke",     "search",       "scrape",       "nickname",
    "scheduler","tasks",    "resilience",   "monitor",      "backup",
    "bumper",   "host",     "multispoof",   "agc",          "gc",
    "webhooks", "automod",  "interactions", "perms",        "db",
    "ai",       "downloads","lastfm",       "protect",
]

CATEGORY_DESC = {
    "general":       "purge, snipe, say, utilities",
    "quests":        "quest enroll + auto complete",
    "sniper":        "snipe deleted/edited messages",
    "afk":           "AFK auto-reply rules",
    "rpc":           "rich presence slots + presets",
    "spoofer":       "platform / device spoof",
    "status":        "custom status + rotation",
    "social":        "friends, block, requests",
    "profile":       "bio, avatar, banner",
    "profile_ext":   "avatar/banner dl, user notes",
    "auto":          "auto + multi react (normal/super), mimic",
    "autoresponder": "keyword / regex replies",
    "filters":       "spam, link, invite, scam filters",
    "loggers":       "delete / edit / join logs",
    "tracking":      "message & profile track",
    "triggers":      "message / reaction triggers",
    "reminders":     "reminders and timers",
    "pingtrack":     "mention counters",
    "guards":        "blacklist + server guard",
    "voice":         "VC mute, move, keep",
    "server":        "ban, kick, channel tools",
    "rolemgmt":      "role info and members",
    "information":   "user / server lookup",
    "settings":      "prefix, aliases, cooldowns",
    "meta":          "config, cogs, uptime",
    "developer":     "eval, plugins, sessions",
    "tools":         "tokeninfo, calc, lyrics",
    "fun":           "memes, jokes, roleplay",
    "utility":       "text tools, translate",
    "mass":          "mass dm / react / friend / report",
        "nuke":          "destructive + backup",
    "search":        "channel search, bulk del",
    "scrape":        "export members / roles",
    "nickname":      "auto nickname",
    "scheduler":     "scheduled messages",
    "tasks":         "background tasks",
    "resilience":    "reconnect + rate limits",
    "monitor":       "event monitors",
    "backup":        "server backup / restore",
    "bumper":        "auto-bump disboard/mee6",
    "host":          "hosted token sessions",
    "multispoof":    "multi-device presence",
    "agc":           "anti group-chat trap",
    "gc":            "group DM tools",
    "webhooks":      "webhooks + emoji steal",
    "automod":       "raid mode, quarantine",
    "interactions":  "buttons and modals",
    "perms":         "permission checks",
    "db":            "notes and history",
    "ai":            "Claude chat",
    "downloads":     "yt / tiktok / insta",
    "lastfm":        "last.fm now playing",
    "protect":       "account danger sweep",
}


@bot.command(name="help", aliases=["h"])
async def _help(ctx, *, query: str = ""):
    from cogs import state as S
    raw  = query.strip().lower()
    pfx  = S.PREFIX
    CPER = 15    # commands per category page
    KPER = 10    # categories per root page

    parts = raw.split()
    page  = 1
    if parts and parts[-1].isdigit():
        page  = max(1, int(parts.pop()))
    q = " ".join(parts)

    cats: dict = {}
    for cog in bot.cogs.values():
        cname = cog.qualified_name.lower()
        cmds  = [c for c in cog.get_commands() if not c.hidden and c.enabled]
        if cmds:
            cats[cname] = sorted(cmds, key=lambda c: c.name)

    def _block(*lines):
        """Render lines as a single Discord ANSI code block."""
        return S._ansi_block(list(lines))

    def _blockquote(content: str) -> str:
        """Wrap content as a blockquote ANSI block (original style)."""
        inner = "\n".join(f"> {l}" for l in content.split("\n"))
        return f"> ```ansi\n{inner}\n> ```"

    if not q:
        seen = set()
        ordered = []
        for name in CATEGORY_ORDER:
            if name in cats and name not in seen:
                ordered.append(name); seen.add(name)
        for name in sorted(cats):
            if name not in seen:
                ordered.append(name); seen.add(name)

        total_cmds = sum(len(v) for v in cats.values())
        pages      = max(1, math.ceil(len(ordered) / KPER))
        page       = min(page, pages)
        chunk      = ordered[(page-1)*KPER : page*KPER]

        lines = [
            f"  {BRAND}wilt{RESET}  {DIM}v{VERSION}{RESET}"
            f"  {GREY}·  {total_cmds} cmds  ·  {len(ordered)} categories{RESET}",
            f"  {DIM}{'─' * 34}{RESET}", "",
        ]
        for cat in chunk:
            n   = len(cats[cat])
            pad = max(0, 14 - len(cat))
            lines.append(
                f"  {CYAN}{cat}{RESET}{' ' * pad}"
                f"  {DIM}{n:>3} cmd{'s' if n != 1 else ''}{RESET}"
            )
        lines += [
            "",
            f"  {DIM}{'─' * 34}{RESET}",
        ]
        nav = f"{pfx}h <category>  ·  {pfx}h <cmd>"
        if pages > 1:
            nxt = (page % pages) + 1
            nav = f"{pfx}h {nxt} → next  ·  " + nav
        lines.append(f"  {DIM}page {page}/{pages}  ·  {nav}{RESET}")
        return await ctx.message.edit(content=S._ansi_block(lines))

    if q in cats:
        cmds  = cats[q]
        pages = max(1, math.ceil(len(cmds) / CPER))
        page  = min(page, pages)
        chunk = cmds[(page-1)*CPER : page*CPER]
        col   = max((len(c.name) for c in chunk), default=8)

        hdr = (f"{BRAND}wilt{RESET}"
               f"{DARK} :: {RESET}"
               f"{WHITE2}v{VERSION}{RESET}"
               f"{DARK} :: {RESET}"
               f"{BLUE2}{q}{RESET}")
        b1 = f"> ```ansi\n> {hdr}\n> ```"

        cmd_lines = []
        for c in chunk:
            pad  = col - len(c.name)
            desc = c.brief or (c.help or "").split("\n")[0] or ""
            cmd_lines.append(
                f"> {CYAN2}{c.name}{' ' * pad}{RESET}"
                f"{DARK} :: {RESET}{WHITE2}{desc}{RESET}")
        b2 = "> ```ansi\n" + "\n".join(cmd_lines) + "\n> ```"

        if pages > 1:
            nxt = (page % pages) + 1
            nav = f"{pfx}h {q} {nxt}"
        else:
            nav = f"{pfx}h <cmd>"
        b3 = (f"> ```ansi\n"
              f"> {DARK}page {page}/{pages}  ·  {nav}  ·  {pfx}h  back to index{RESET}\n"
              f"> ```")

        return await ctx.message.edit(content="\n".join([b1, b2, b3]))

    cmd = bot.get_command(q)
    if cmd:
        cog_name = cmd.cog.qualified_name.lower() if cmd.cog else "—"
        als      = "  ".join(f"{pfx}{a}" for a in cmd.aliases) if cmd.aliases else "—"
        sig      = cmd.signature or ""
        desc     = cmd.help or cmd.brief or "no description"

        lines = [
            f"  {WHITE}{pfx}{cmd.name}"
            + (f"  {GREY}{sig}{RESET}" if sig else f"{RESET}"),
            f"  {DIM}{'─' * 34}{RESET}", "",
            f"  {GREY}category{RESET}  {CYAN}{cog_name}{RESET}",
            f"  {GREY}aliases {RESET}  {DIM}{als}{RESET}",
            "",
            f"  {WHITE2}{desc}{RESET}",
        ]
        if hasattr(cmd, "commands"):
            subs = sorted(cmd.commands, key=lambda c: c.name)
            if subs:
                lines += ["", f"  {GREY}sub-commands{RESET}"]
                col2 = max(len(s.name) for s in subs)
                for sub in subs:
                    pad = col2 - len(sub.name)
                    lines.append(
                        f"  {GREY}├ {CYAN2}{sub.name}{RESET}{' ' * pad}"
                        f"  {DIM}{sub.brief or ''}{RESET}")
        lines += [
            "",
            f"  {DIM}{'─' * 34}{RESET}",
            f"  {DIM}{pfx}h {cog_name}  ·  back to category{RESET}",
        ]
        return await ctx.message.edit(content=S._ansi_block(lines))

    all_cmds = [c for cog in bot.cogs.values() for c in cog.get_commands()]
    matches  = [c for c in all_cmds
                if q in c.name or c.name.startswith(q[:3])][:8]
    if matches:
        lines = [
            f"  {RED}✗{RESET}  unknown: {WHITE}{q}{RESET}",
            f"  {DIM}{'─' * 34}{RESET}", "",
            f"  {GREY}did you mean?{RESET}", "",
        ]
        for c in matches:
            cg  = c.cog.qualified_name.lower() if c.cog else "?"
            pad = max(0, 18 - len(c.name))
            lines.append(
                f"  {CYAN2}{pfx}{c.name}{RESET}{' ' * pad}"
                f"  {DIM}{c.brief or ''}  [{cg}]{RESET}")
        return await ctx.message.edit(content=S._ansi_block(lines))

    await ctx.message.edit(
        content=S.ui_err(f"unknown command or category: `{q}`"))


@bot.command(name="ping")
async def _ping(ctx):
    from cogs import state as S
    ms = round(bot.latency * 1000)
    try:
        hist = getattr(S, "_latency_history", None)
        if hist is None:
            S._latency_history = []
            hist = S._latency_history
        hist.append(ms)
        if len(hist) > 50:
            del hist[:-50]
        avg = sum(hist) / len(hist)
        await ctx.message.edit(content=S.ui_ok(f"pong — `{ms}ms` (avg `{avg:.0f}ms`)"))
    except Exception:
        await ctx.message.edit(content=S.ui_ok(f"pong — `{ms}ms`"))

if not TOKEN:
    sys.exit("TOKEN not set — add to config.json or TOKEN env var")

bot.run(TOKEN, log_handler=None)
