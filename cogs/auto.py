import asyncio
import urllib.parse
import discord
from discord.ext import commands
from . import state as S
from .antid import jitter


async def _put_reaction(message, emoji: str, *, burst: bool = False) -> bool:
    """
    PUT reaction on a message.
    burst=False → normal (type=0)
    burst=True  → super/burst (type=1, Nitro)
    """
    import aiohttp
    em = (emoji or "").strip()
    if not em:
        return False
    if em.startswith("<") and ":" in em:
        parts = em.strip("<>").split(":")
        if len(parts) >= 3:
            em = f"{parts[1]}:{parts[2]}"
    em_enc = urllib.parse.quote(em, safe="")
    typ = 1 if burst else 0
    url = (
        f"https://discord.com/api/v9/channels/{message.channel.id}"
        f"/messages/{message.id}/reactions/{em_enc}/@me"
        f"?location=Message%20Reaction%20Picker&type={typ}"
    )
    token = S.TOKEN or getattr(getattr(S, "BOT", None), "http", None) and getattr(S.BOT.http, "token", None)
    if not token:
        print("[auto] put_reaction: no TOKEN")
        return False
    headers = {
        "Authorization": token,
        "User-Agent": S.USER_AGENT,
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.put(url, headers=headers) as r:
                if r.status in (200, 201, 204):
                    return True
                body = await r.text()
                print(f"[auto] put_reaction {r.status} type={typ} em={em[:30]!r}: {body[:150]}")
                return False
    except Exception as e:
        print(f"[auto] put_reaction err: {e}")
        return False


async def _react(message, emoji: str, *, burst: bool = False) -> bool:
    """Try burst HTTP, then normal HTTP, then library add_reaction."""
    if burst:
        if await _put_reaction(message, emoji, burst=True):
            return True
    if await _put_reaction(message, emoji, burst=False):
        return True
    try:
        await message.add_reaction(emoji)
        return True
    except Exception as e:
        print(f"[auto] add_reaction fallback: {e}")
        return False


def _parse_mode(s: str):
    if not s:
        return None
    t = s.lower().strip()
    if t in ("super", "s", "burst", "sr", "nitro"):
        return "super"
    if t in ("regular", "r", "normal", "n", "reg"):
        return "regular"
    return None


def _parse_user_token(s: str):
    if not s:
        return None
    t = s.strip()
    if t.startswith("<@") and t.endswith(">"):
        t = t[2:-1].lstrip("!")
    if t.isdigit() and len(t) >= 15:
        return int(t)
    return None


def _parse_react_args(args: str):
    parts = (args or "").split()
    emoji = parts[0] if parts else ""
    mode = "regular"
    user_id = None
    for p in parts[1:]:
        m = _parse_mode(p)
        if m:
            mode = m
            continue
        uid = _parse_user_token(p)
        if uid is not None:
            user_id = uid
            continue
    return emoji, mode, user_id


class AutoCog(commands.Cog, name="auto"):
    """Auto-react / multi-react (normal + super), mimic, autoaddback."""

    def __init__(self, bot):
        self.bot = bot

    def _ar_status_rows(self):
        rows = []
        g = S.AUTO_RESPONSES.get("react", {}) or {}
        if g.get("global"):
            rows.append(
                f"  {S.GREY}•{S.RESET} you  {g['global']}  "
                f"{S.DIM}{g.get('global_mode', 'regular')}{S.RESET}"
            )
        for uid, data in (S._autoreact_users or {}).items():
            if isinstance(data, dict):
                rows.append(
                    f"  {S.GREY}•{S.RESET} <@{uid}>  {data.get('emoji')}  "
                    f"{S.DIM}{data.get('mode', 'regular')}{S.RESET}"
                )
            else:
                rows.append(f"  {S.GREY}•{S.RESET} <@{uid}>  {data}  {S.DIM}regular{S.RESET}")
        return rows

    def _mr_status_rows(self):
        mr = S.AUTO_RESPONSES.get("multireact", {}) or {}
        rows = []
        if mr.get("enabled") or mr.get("emojis"):
            mode = mr.get("mode", "regular")
            uid = mr.get("user_id")
            self_only = mr.get("self_only", uid is None)
            target = "you" if self_only else (f"<@{uid}>" if uid else "everyone")
            ems = " ".join(mr.get("emojis", []) or [])
            rows.append(f"  {S.GREY}•{S.RESET} {ems or '—'}  {S.DIM}{mode}{S.RESET}  → {target}")
        return rows

    @commands.command(name="autoreact", brief="Auto-react YOUR messages: emoji [super|regular]")
    async def autoreact(self, ctx, *, args: str = ""):
        raw = (args or "").strip()
        if not raw:
            rows = self._ar_status_rows()
            return await ctx.message.edit(
                content=S._paginate("autoreact", "emoji [super|regular] | clear", rows)
                if rows else S.ui_info("off — usage: .autoreact <emoji> [super|regular]")
            )

        low = raw.lower()
        if low in ("clear", "off", "reset") or low.startswith("clear "):
            rest = raw.split(None, 1)[1] if " " in raw else ""
            uid = _parse_user_token(rest) if rest else None
            if uid is not None:
                S._autoreact_users.pop(uid, None)
                return await ctx.message.edit(content=S.ui_ok(f"autoreact cleared for <@{uid}>"))
            S.AUTO_RESPONSES.pop("react", None)
            S._autoreact_users.clear()
            return await ctx.message.edit(content=S.ui_ok("autoreact cleared"))

        emoji, mode, user_id = _parse_react_args(raw)
        if not emoji or _parse_mode(emoji) or _parse_user_token(emoji):
            return await ctx.message.edit(
                content=S.ui_err("usage: .autoreact <emoji> [super|regular]")
            )

        if user_id is not None:
            S._autoreact_users[user_id] = {"emoji": emoji, "mode": mode}
            await ctx.message.edit(
                content=S.ui_ok(f"autoreact → {emoji} ({mode}) for <@{user_id}>")
            )
        else:
            S.AUTO_RESPONSES.setdefault("react", {})["global"] = emoji
            S.AUTO_RESPONSES["react"]["global_mode"] = mode
            await ctx.message.edit(
                content=S.ui_ok(f"autoreact → {emoji} ({mode}) on your messages")
            )

        try:
            await asyncio.sleep(0.05)
            await _react(ctx.message, emoji, burst=(mode == "super"))
        except Exception as e:
            print(f"[auto] confirm react: {e}")

    @commands.command(name="multireact", aliases=["mr"], brief="Multi-react YOUR messages: emojis [super|regular]")
    async def multireact(self, ctx, *, args: str = ""):
        raw = (args or "").strip()
        if not raw:
            rows = self._mr_status_rows()
            return await ctx.message.edit(
                content=S._paginate("multireact", "emojis [super|regular] | clear", rows)
                if rows else S.ui_info("off — usage: .multireact <emoji...> [super|regular]")
            )

        low = raw.lower()
        if low in ("clear", "off", "reset", "disable"):
            S.AUTO_RESPONSES.pop("multireact", None)
            return await ctx.message.edit(content=S.ui_ok("multireact cleared"))

        parts = raw.split()
        mode = "regular"
        user_id = None
        emojis = []
        for p in parts:
            m = _parse_mode(p)
            if m:
                mode = m
                continue
            uid = _parse_user_token(p)
            if uid is not None:
                user_id = uid
                continue
            emojis.append(p)

        if not emojis:
            return await ctx.message.edit(
                content=S.ui_err("usage: .multireact <emoji...> [super|regular]")
            )

        S.AUTO_RESPONSES["multireact"] = {
            "enabled": True,
            "emojis": emojis,
            "mode": mode,
            "user_id": user_id,
            "self_only": user_id is None,
        }
        target = f"<@{user_id}>" if user_id is not None else "your messages"
        await ctx.message.edit(
            content=S.ui_ok(f"multireact → {' '.join(emojis)} ({mode}) → {target}")
        )

        try:
            await asyncio.sleep(0.05)
            burst = mode == "super"
            for em in emojis[:5]:
                await _react(ctx.message, em, burst=burst)
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[auto] mr confirm: {e}")

    @commands.command(name="mimic", brief="Mimic a user in this channel")
    async def mimic(self, ctx, user: discord.User = None):
        if not user:
            return await ctx.message.edit(content=S.ui_err("usage: mimic <@user>"))
        S._mimic_dict[ctx.channel.id] = user.id
        await ctx.message.edit(content=S.ui_ok(f"mimicking {user}"))

    @commands.command(name="unmimic", brief="Stop mimicking in this channel")
    async def unmimic(self, ctx):
        S._mimic_dict.pop(ctx.channel.id, None)
        await ctx.message.edit(content=S.ui_ok("mimic stopped"))

    @commands.command(name="stopmimic", brief="Stop all mimics")
    async def stopmimic(self, ctx):
        S._mimic_dict.clear()
        await ctx.message.edit(content=S.ui_ok("all mimics stopped"))

    @commands.command(name="autoaddback", brief="Toggle auto friend-accept")
    async def autoaddback(self, ctx, toggle: str = ""):
        if toggle:
            S._autoaddback = toggle.lower() not in ("off", "disable", "false", "0")
        else:
            S._autoaddback = not getattr(S, "_autoaddback", False)
        await ctx.message.edit(content=S.ui_ok(f"autoaddback → {'on' if S._autoaddback else 'off'}"))

    @commands.command(name="nitrosniper", brief="Toggle Nitro link sniper")
    async def nitrosniper(self, ctx, toggle: str = ""):
        if toggle:
            S._nitrosniper_enabled = toggle.lower() not in ("off", "disable", "false", "0")
        else:
            S._nitrosniper_enabled = not getattr(S, "_nitrosniper_enabled", True)
        await ctx.message.edit(
            content=S.ui_ok(f"nitro sniper → {'on' if S._nitrosniper_enabled else 'off'}")
        )

    @commands.command(name="vsniper", brief="Toggle vanity URL sniper")
    async def vsniper(self, ctx, toggle: str = ""):
        if not hasattr(S, "_vsniper_enabled"):
            S._vsniper_enabled = False
        if toggle:
            S._vsniper_enabled = toggle.lower() not in ("off", "disable", "false", "0")
        else:
            S._vsniper_enabled = not S._vsniper_enabled
        await ctx.message.edit(
            content=S.ui_ok(f"vsniper → {'on' if S._vsniper_enabled else 'off'}")
        )

    async def _apply_reacts(self, message, *, is_self: bool):
        """Shared path for autoreact + multireact."""
        emoji = mode = None
        entry = (S._autoreact_users or {}).get(message.author.id)
        if isinstance(entry, dict):
            emoji = entry.get("emoji")
            mode = entry.get("mode", "regular")
        elif entry:
            emoji, mode = entry, "regular"
        if not emoji and is_self:
            g = S.AUTO_RESPONSES.get("react", {}) or {}
            emoji = g.get("global")
            mode = g.get("global_mode", "regular")
        if emoji:
            try:
                await asyncio.sleep(0.05)
                await _react(message, emoji, burst=(mode == "super"))
            except Exception as e:
                print(f"[auto] react fail: {e}")

        mr = S.AUTO_RESPONSES.get("multireact", {}) or {}
        if mr.get("enabled") and mr.get("emojis"):
            target = mr.get("user_id")
            self_only = mr.get("self_only", target is None)
            match = is_self if self_only else (message.author.id == target)
            if match:
                burst = mr.get("mode", "regular") == "super"
                for em in mr["emojis"]:
                    try:
                        await asyncio.sleep(0.05)
                        await _react(message, em, burst=burst)
                    except Exception as e:
                        print(f"[auto] multireact fail: {e}")

    async def _handle_self_message(self, message):
        """Called from WiltBot.on_message for own messages (reliable path)."""
        await self._apply_reacts(message, is_self=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.bot.user:
            return
        me = self.bot.user.id
        is_self = message.author.id == me

        if is_self:
            return

        uid = S._mimic_dict.get(message.channel.id)
        if uid and message.author.id == uid:
            try:
                await asyncio.sleep(jitter(1.2))
                if message.content:
                    await message.channel.send(message.content)
            except Exception:
                pass

        await self._apply_reacts(message, is_self=False)


    @commands.command(name="rotatename", brief="Rotate display name every 5s")
    async def rotatename(self, ctx, *, names: str = ""):
        if not names or names.lower() in ("off", "stop", "clear"):
            t = getattr(self, "_name_rot_task", None)
            if t and not t.done():
                t.cancel()
            self._name_rot_task = None
            return await ctx.message.edit(content=S.ui_ok("name rotation stopped"))
        parts = [p.strip() for p in names.replace("|", ",").split(",") if p.strip()]
        if len(parts) < 2:
            return await ctx.message.edit(content=S.ui_err("usage: rotatename name1, name2, name3"))
        t = getattr(self, "_name_rot_task", None)
        if t and not t.done():
            t.cancel()

        async def _loop():
            i = 0
            while True:
                try:
                    name = parts[i % len(parts)][:32]
                    await self.bot.user.edit(global_name=name)
                except Exception as e:
                    print(f"[auto] rotatename: {e}")
                i += 1
                await asyncio.sleep(5)

        self._name_rot_task = asyncio.create_task(_loop())
        await ctx.message.edit(content=S.ui_ok(f"rotating names every 5s ({len(parts)} names)"))

    @commands.command(name="rotateservername", brief="Rotate a server name every 5s")
    async def rotateservername(self, ctx, *, names: str = ""):
        if not ctx.guild:
            return await ctx.message.edit(content=S.ui_err("server only"))
        if not names or names.lower() in ("off", "stop", "clear"):
            tasks = getattr(self, "_sname_rot_tasks", {})
            t = tasks.pop(ctx.guild.id, None)
            if t and not t.done():
                t.cancel()
            return await ctx.message.edit(content=S.ui_ok("server name rotation stopped"))
        parts = [p.strip() for p in names.replace("|", ",").split(",") if p.strip()]
        if len(parts) < 2:
            return await ctx.message.edit(content=S.ui_err("usage: rotateservername name1, name2"))
        if not hasattr(self, "_sname_rot_tasks"):
            self._sname_rot_tasks = {}
        old = self._sname_rot_tasks.get(ctx.guild.id)
        if old and not old.done():
            old.cancel()
        guild = ctx.guild

        async def _loop():
            i = 0
            while True:
                try:
                    await guild.edit(name=parts[i % len(parts)][:100])
                except Exception as e:
                    print(f"[auto] rotateservername: {e}")
                    await asyncio.sleep(15)
                i += 1
                await asyncio.sleep(5)

        self._sname_rot_tasks[guild.id] = asyncio.create_task(_loop())
        await ctx.message.edit(content=S.ui_ok(f"rotating server name every 5s ({len(parts)} names)"))


async def setup(bot):
    await bot.add_cog(AutoCog(bot))
