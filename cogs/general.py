import asyncio, time, discord
from discord.ext import commands
from . import state as S
from .antid import delay, on_rate_limit, jitter

class GeneralCog(commands.Cog, name="general"):
    """General utilities and account commands."""
    def __init__(self, bot): self.bot = bot

    @commands.command(name="stats", brief="Account stats")
    async def stats(self, ctx):
        u = ctx.author
        rows = [
            f"  {S.DIM}tag{S.RESET}      {u}",
            f"  {S.DIM}id{S.RESET}       {u.id}",
            f"  {S.DIM}guilds{S.RESET}   {len(self.bot.guilds)}",
            f"  {S.DIM}latency{S.RESET}  {round(self.bot.latency*1000)}ms",
        ]
        await ctx.message.edit(content=S.ui_box("wilt stats", rows))

    @commands.command(name="clrmsgs", aliases=["clr"], brief="Delete your own messages")
    async def purge(self, ctx, amount: int = 10):
        ctx._wilt_skip_delete = True  # already deleting ourselves
        try:
            await ctx.message.delete()
        except Exception:
            pass
        deleted = 0
        async for msg in ctx.channel.history(limit=200):
            if msg.author.id == self.bot.user.id and deleted < amount:
                try:
                    await msg.delete()
                    deleted += 1
                    await delay(0.3, 0.9)
                except Exception as e:
                    if "429" in str(e): await on_rate_limit(5.0)
        conf = await ctx.channel.send(S.ui_ok(f"deleted {deleted} message(s)"))
        await asyncio.sleep(3)
        try: await conf.delete()
        except Exception: pass

    @commands.command(name="snipe", brief="Show last deleted message")
    async def snipe(self, ctx):
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await ctx.message.edit(content=S.ui_info("nothing to snipe"))
        rows = [
            f"  {S.DIM}author{S.RESET}  {entry.get('author','?')}",
            f"  {S.DIM}content{S.RESET} {entry.get('content','')[:200]}",
        ]
        await ctx.message.edit(content=S.ui_box("snipe", rows))



    @commands.command(name="hypesquad", brief="Set HypeSquad house")
    async def hypesquad(self, ctx, house: str = ""):
        import aiohttp
        house = house.lower()
        houses = {"bravery": 1, "brilliance": 2, "balance": 3}
        hid = houses.get(house)
        if not hid:
            return await ctx.message.edit(content=S.ui_err("usage: hypesquad <bravery|brilliance|balance>"))
        h = {"Authorization": S.TOKEN, "Content-Type": "application/json", "User-Agent": S.USER_AGENT}
        async with aiohttp.ClientSession() as s:
            async with s.post("https://discord.com/api/v9/hypesquad/online",
                              headers=h, json={"house_id": hid}) as r:
                if r.status in (200, 204):
                    await ctx.message.edit(content=S.ui_ok(f"HypeSquad → {house.title()}"))
                else:
                    await ctx.message.edit(content=S.ui_err(f"failed ({r.status})"))


    @commands.command(name="firstmessage", aliases=["fm"], brief="Jump to first message")
    async def firstmessage(self, ctx):
        async for msg in ctx.channel.history(limit=1, oldest_first=True):
            await ctx.message.edit(content=msg.jump_url)


    @commands.command(name="say", brief="Send a message as yourself")
    async def say(self, ctx, *, text: str = ""):
        await ctx.message.delete()
        if text: await ctx.channel.send(text)

    @commands.command(name="copycat", brief="Repeat the last message in channel")
    async def copycat(self, ctx):
        async for msg in ctx.channel.history(limit=5):
            if msg.id != ctx.message.id and msg.content:
                await ctx.message.edit(content=msg.content)
                return
        await ctx.message.edit(content=S.ui_err("nothing to copy"))

    @commands.command(name="spam", brief="Spam a message N times (async, no max)")
    async def spam(self, ctx, n: int = 5, *, text: str = ""):
        if not text:
            return await ctx.message.edit(content=S.ui_err("usage: spam <count> <text>"))
        try:
            n = int(n)
        except (TypeError, ValueError):
            return await ctx.message.edit(content=S.ui_err("usage: spam <count> <text>"))
        n = max(1, n)
        await ctx.message.delete()
        import asyncio as _a

        async def _one():
            try:
                await ctx.channel.send(text)
            except Exception:
                pass

        wave = 8  # parallel sends per wave
        for start in range(0, n, wave):
            batch = [_one() for _ in range(min(wave, n - start))]
            await _a.gather(*batch)
            if start + wave < n:
                await _a.sleep(jitter(0.05))

    @commands.command(name="spamstop", brief="Spam placeholder (use Ctrl+C)")
    async def spamstop(self, ctx):
        await ctx.message.edit(content=S.ui_info("stop active tasks with .task clear"))

    @commands.command(name="info", brief="Bot info")
    async def info(self, ctx):
        await ctx.message.edit(content=S.ui_box("wilt", [
            f"  {S.DIM}version{S.RESET}  {S.VERSION}",
            f"  {S.DIM}lib{S.RESET}      discord.py-self",
            f"  {S.DIM}guilds{S.RESET}   {len(self.bot.guilds)}",
            f"  {S.DIM}latency{S.RESET}  {round(self.bot.latency*1000)}ms",
        ]))


    @commands.command(name="purgeall", brief="Delete ALL your messages in channel")
    async def purgeall(self, ctx):
        await ctx.message.delete()
        import asyncio as _a
        deleted = 0
        async for msg in ctx.channel.history(limit=1000):
            if msg.author.id == self.bot.user.id:
                try: await msg.delete(); deleted += 1
                except Exception: pass
                await _a.sleep(0.3)
        m = await ctx.channel.send(S.ui_ok(f"deleted {deleted}"))
        await _a.sleep(3)
        try: await m.delete()
        except Exception: pass

    @commands.command(name="readlog", brief="Show the bot's log file tail")
    async def readlog(self, ctx, n: int = 10):
        import os
        lf = getattr(S,"LOG_FILE","wilt.log")
        if not os.path.exists(lf): return await ctx.message.edit(content=S.ui_err("no log file"))
        with open(lf,"r",errors="replace") as f: lines = f.readlines()
        tail = "".join(lines[-n:])[-1900:]
        nl = chr(10)
        await ctx.message.edit(content=f"```{nl}{tail}{nl}```")

    @commands.command(name="sniper", brief="Toggle nitro/giveaway sniper")
    async def sniper(self, ctx, sub: str = "", toggle: str = ""):
        if sub == "nitro":
            S._nitrosniper_enabled = toggle.lower() not in ("off","disable") if toggle else not S._nitrosniper_enabled
            return await ctx.message.edit(content=S.ui_ok(f"nitro sniper → {'on' if S._nitrosniper_enabled else 'off'}"))
        if sub == "giveaway":
            S._giveaway_enabled = toggle.lower() not in ("off","disable") if toggle else not getattr(S,"_giveaway_enabled",False)
            return await ctx.message.edit(content=S.ui_ok(f"giveaway sniper → {'on' if S._giveaway_enabled else 'off'}"))
        await ctx.message.edit(content=S.ui_box("snipers",[
            f"  {S.DIM}nitro{S.RESET}    {S._nitrosniper_enabled}",
            f"  {S.DIM}giveaway{S.RESET} {getattr(S,'_giveaway_enabled',False)}",
        ]))

    @commands.command(name="report", brief="Report a user via Discord API")
    async def report(self, ctx, user: discord.User = None, reason: str = "spam"):
        if not user:
            return await ctx.message.edit(content=S.ui_err("usage: report <@user> [spam|illegal|harassment|malware]"))
        reason_map = {"spam": 1, "illegal": 3, "harassment": 4, "malware": 5, "other": 1}
        key = (reason or "spam").lower()
        reason_type = reason_map.get(key, 1)
        token = S.TOKEN or getattr(getattr(self.bot, "http", None), "token", "")
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": getattr(S, "USER_AGENT", "Mozilla/5.0"),
        }
        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"https://discord.com/api/v9/users/{user.id}/report",
                    headers=headers,
                    json={"reason": reason_type, "version": "1.0"},
                ) as r:
                    if r.status in (200, 201, 204):
                        await ctx.message.edit(content=S.ui_ok(f"reported {user} ({key})"))
                    elif r.status == 429:
                        await ctx.message.edit(content=S.ui_err("rate limited"))
                    else:
                        await ctx.message.edit(content=S.ui_err(f"report failed ({r.status})"))
        except Exception as e:
            await ctx.message.edit(content=S.ui_err(str(e)[:120]))


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
