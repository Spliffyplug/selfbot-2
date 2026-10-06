import time
import asyncio
import discord
from discord.ext import commands
from . import state as S


class AfkCog(commands.Cog, name="afk"):
    def __init__(self, bot):
        self.bot = bot
        self._system_msg_ids: set[int] = set()

    def _is_command_message(self, message) -> bool:
        """True if message looks like a bot command (prefix or valid ctx)."""
        content = (message.content or "").lstrip()
        prefixes = (
            S.PREFIX,
            str(getattr(self.bot, "command_prefix", ".")),
        )
        if any(content.startswith(p) for p in prefixes if p):
            return True
        try:
            return False
        except Exception:
            return False

    async def _is_valid_cmd(self, message) -> bool:
        try:
            ctx = await self.bot.get_context(message)
            return bool(ctx.valid)
        except Exception:
            return False

    def _references_system_msg(self, message) -> bool:
        """True if this message is a reply to one of our AFK/welcome system messages."""
        ref = getattr(message, "reference", None)
        if not ref:
            return False
        mid = getattr(ref, "message_id", None)
        if mid and mid in self._system_msg_ids:
            return True
        return False

    @commands.command(name="afk", brief="Set AFK message")
    async def afk(self, ctx, *, msg: str = "I'm AFK"):
        S.afk["enabled"] = True
        S.afk["emergency"] = False
        S.afk["message"] = msg
        S.afk["since"] = time.time()
        S.afk["ping_counter"] = {}
        S.afk["last_reply"] = {}
        try:
            S.save_afk()
        except Exception:
            pass
        await ctx.message.edit(content=S.ui_ok(f"AFK on — {msg}"))

    @commands.command(name="afkreturn", brief="Return from AFK")
    async def afkreturn(self, ctx):
        S.afk["enabled"] = False
        S.afk["emergency"] = False
        S.afk["ping_counter"].clear()
        S.afk["last_reply"].clear()
        try:
            S.save_afk()
        except Exception:
            pass
        await ctx.message.edit(content=S.ui_ok("AFK cleared — welcome back"))

    @commands.command(name="afkwhitelist", brief="Whitelist a user from AFK replies")
    async def afkwhitelist(self, ctx, user: discord.User = None):
        if not user:
            return await ctx.message.edit(content=S.ui_err("usage: afkwhitelist <@user>"))
        S.afk["whitelist"].add(user.id)
        await ctx.message.edit(content=S.ui_ok(f"whitelisted {user}"))

    @commands.command(name="afkblacklist", brief="Blacklist a user from AFK replies")
    async def afkblacklist(self, ctx, user: discord.User = None):
        if not user:
            return await ctx.message.edit(content=S.ui_err("usage: afkblacklist <@user>"))
        S.afk["blacklist"].add(user.id)
        await ctx.message.edit(content=S.ui_ok(f"blacklisted {user}"))

    @commands.command(name="afkignore", aliases=["afkignorelist"], brief="List AFK blacklist")
    async def afkignore(self, ctx):
        rows = [f"  {S.GREY}•{S.RESET} {uid}" for uid in S.afk["blacklist"]]
        await ctx.message.edit(
            content=S._paginate("afk blacklist", "", rows) if rows else S.ui_info("empty")
        )

    @commands.command(name="afkdmonly", brief="AFK in DMs only toggle")
    async def afkdmonly(self, ctx, toggle: str = ""):
        if toggle:
            S.afk["dm_only"] = toggle.lower() not in ("off", "disable", "false", "0")
        else:
            S.afk["dm_only"] = not S.afk.get("dm_only", False)
        await ctx.message.edit(content=S.ui_ok(f"AFK DM-only → {S.afk['dm_only']}"))

    @commands.command(name="afkemergency", brief="Emergency AFK")
    async def afkemergency(self, ctx, *, msg: str = "Emergency AFK"):
        S.afk["enabled"] = True
        S.afk["emergency"] = True
        S.afk["message"] = msg
        await ctx.message.edit(content=S.ui_ok(f"Emergency AFK: {msg}"))

    @commands.command(name="afkcooldown", brief="Set AFK reply cooldown")
    async def afkcooldown(self, ctx, seconds: int = 30):
        S.afk["cooldown"] = max(0, seconds)
        await ctx.message.edit(content=S.ui_ok(f"AFK cooldown → {seconds}s"))

    @commands.command(name="afkexpire", brief="Set AFK auto-expire minutes")
    async def afkexpire(self, ctx, minutes: int = 0):
        S.afk["expires_at"] = time.time() + minutes * 60 if minutes > 0 else 0
        await ctx.message.edit(
            content=S.ui_ok(f"AFK expires in {minutes}m" if minutes else "AFK no expiry")
        )

    @commands.command(name="afkcustom", brief="Custom AFK reply for a user")
    async def afkcustom(self, ctx, user: discord.User = None, *, reply: str = ""):
        if not user or not reply:
            return await ctx.message.edit(content=S.ui_err("usage: afkcustom <@user> <reply>"))
        S.afk["custom_replies"][str(user.id)] = reply
        await ctx.message.edit(content=S.ui_ok(f"custom reply for {user}: {reply[:40]}"))

    @commands.command(name="afkpingcount", brief="Show pings while AFK")
    async def afkpingcount(self, ctx):
        total = sum(S.afk["ping_counter"].values())
        rows = [
            f"  {S.GREY}•{S.RESET} <@{uid}> × {n}"
            for uid, n in sorted(S.afk["ping_counter"].items(), key=lambda x: -x[1])[:10]
        ]
        await ctx.message.edit(content=S.ui_box(f"pings while AFK ({total} total)", rows))

    @commands.command(name="afkserver", brief="Server-specific AFK message")
    async def afkserver(self, ctx, *, msg: str = ""):
        if not ctx.guild:
            return await ctx.message.edit(content=S.ui_err("server only"))
        gid = str(ctx.guild.id)
        if msg:
            S.afk["per_server"][gid] = msg
            await ctx.message.edit(content=S.ui_ok(f"server AFK → {msg}"))
        else:
            S.afk["per_server"].pop(gid, None)
            await ctx.message.edit(content=S.ui_ok("server AFK cleared"))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.bot.user:
            return

        me = self.bot.user.id

        if message.author.id == me:
            if message.id in self._system_msg_ids:
                return
            content = (message.content or "").strip()
            if not content:
                return
            if content.startswith(
                (S.PREFIX, str(getattr(self.bot, "command_prefix", ".")))
            ):
                return
            if getattr(message, "reference", None):
                if self._references_system_msg(message):
                    return

            if S.afk.get("enabled"):
                is_cmd = await self._is_valid_cmd(message)
                if not is_cmd:
                    S.afk["enabled"] = False
                    S.afk["emergency"] = False
                    S.afk["ping_counter"].clear()
                    S.afk["last_reply"].clear()
                    try:
                        S.save_afk()
                    except Exception:
                        pass
                    try:
                        wb = await message.channel.send(
                            f"welcome back <@{me}>"
                        )
                        self._system_msg_ids.add(wb.id)
                        if len(self._system_msg_ids) > 200:
                            self._system_msg_ids = set(list(self._system_msg_ids)[-100:])
                        await asyncio.sleep(5)
                        try:
                            await wb.delete()
                            self._system_msg_ids.discard(wb.id)
                        except Exception:
                            pass
                    except Exception:
                        pass
            return

        if not S.afk.get("enabled"):
            return

        if self._references_system_msg(message):
            return

        exp = S.afk.get("expires_at") or 0
        if exp and time.time() > exp:
            S.afk["enabled"] = False
            return

        if S.afk.get("dm_only") and message.guild:
            return
        if message.author.id in S.afk.get("blacklist", set()):
            return

        wl = S.afk.get("whitelist") or set()
        if wl and message.author.id not in wl and not S.afk.get("emergency"):
            return

        mentions = message.mentions or []
        if not S.afk.get("emergency") and not any(m.id == me for m in mentions):
            return

        uid = str(message.author.id)
        last = S.afk["last_reply"].get(uid, 0)
        if time.time() - last < S.afk.get("cooldown", 30):
            return
        S.afk["last_reply"][uid] = time.time()
        S.afk["ping_counter"][uid] = S.afk["ping_counter"].get(uid, 0) + 1

        reply = S.afk.get("custom_replies", {}).get(uid) or S.afk.get("message", "I'm AFK")
        if message.guild and str(message.guild.id) in S.afk.get("per_server", {}):
            reply = S.afk["per_server"][str(message.guild.id)]

        try:
            sent = await message.channel.send(S.ui_info(reply))
            self._system_msg_ids.add(sent.id)
            if len(self._system_msg_ids) > 200:
                self._system_msg_ids = set(list(self._system_msg_ids)[-100:])
            await asyncio.sleep(5)
            try:
                await sent.delete()
                self._system_msg_ids.discard(sent.id)
            except Exception:
                pass
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AfkCog(bot))
