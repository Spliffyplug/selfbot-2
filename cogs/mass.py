import asyncio
import os
import discord
from discord.ext import commands
from . import state as S
from .antid import batch_delay, shuffled, on_rate_limit, delay

def _safe_int(val, default=1, lo=1, hi=None):
    try:
        n = int(val)
    except (TypeError, ValueError):
        n = default
    n = max(lo, n)
    if hi is not None:
        n = min(n, hi)
    return n

class MassCog(commands.Cog, name="mass"):
    def __init__(self, bot):
        self.bot = bot
        self._dm_task = None          # cancellable massdm task
        self._abort = asyncio.Event() # shared abort flag for long runs

    def _reset_abort(self):
        self._abort = asyncio.Event()

    @commands.command(name="massban", brief="Mass ban users")
    @commands.guild_only()
    async def massban(self, ctx, *members: discord.Member):
        if not members:
            return await ctx.message.edit(content=S.ui_err("provide users to ban"))
        await ctx.message.edit(content=S.ui_info(f"banning {len(members)}..."))
        done = 0
        for i, m in enumerate(shuffled(members)):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.ban(m, reason="massban")
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f"banned {done}/{len(members)}"))

    @commands.command(name="masskick", brief="Mass kick users")
    @commands.guild_only()
    async def masskick(self, ctx, *members: discord.Member):
        if not members:
            return await ctx.message.edit(content=S.ui_err("provide users to kick"))
        await ctx.message.edit(content=S.ui_info(f"kicking {len(members)}..."))
        done = 0
        for i, m in enumerate(shuffled(members)):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.kick(m, reason="masskick")
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f"kicked {done}/{len(members)}"))

    @commands.command(name="massrole", brief="Add role to many users")
    @commands.guild_only()
    async def massrole(self, ctx, role: discord.Role = None, *members: discord.Member):
        if not role:
            return await ctx.message.edit(content=S.ui_err("usage: massrole <@role> <@users...>"))
        if members:
            targets = list(members)
        else:
            targets = [m for m in ctx.guild.members if not m.bot]
            if len(targets) > 100:
                return await ctx.message.edit(
                    content=S.ui_err(f"{len(targets)} members — pass users explicitly or use smaller scope"))
        done = 0
        for i, m in enumerate(shuffled(targets)):
            if self._abort.is_set():
                break
            try:
                await m.add_roles(role)
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.message.edit(content=S.ui_ok(f"added {role.name} to {done} members"))

    @commands.command(name="massunrole", brief="Remove role from many users")
    @commands.guild_only()
    async def massunrole(self, ctx, role: discord.Role = None, *members: discord.Member):
        if not role:
            return await ctx.message.edit(content=S.ui_err("usage: massunrole <@role> <@users...>"))
        if members:
            targets = list(members)
        else:
            targets = [m for m in ctx.guild.members if role in m.roles]
            if len(targets) > 100:
                return await ctx.message.edit(
                    content=S.ui_err(f"{len(targets)} members with role — pass users explicitly"))
        done = 0
        for i, m in enumerate(shuffled(targets)):
            if self._abort.is_set():
                break
            try:
                await m.remove_roles(role)
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.message.edit(content=S.ui_ok(f"removed {role.name} from {done} members"))

    @commands.command(name="massch", brief="Create N text channels")
    @commands.guild_only()
    async def massch(self, ctx, name: str = "channel", n: int = 5):
        n = _safe_int(n, 5, 1, 25)
        await ctx.message.edit(content=S.ui_info(f"creating {n} channels..."))
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_text_channel(f"{name}-{i + 1}")
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.message.edit(content=S.ui_ok(f"created {done}/{n} channels"))

    @commands.command(name="masscat", brief="Create N categories in server")
    @commands.guild_only()
    async def masscat(self, ctx, name: str = "Category", n: int = 5):
        n = _safe_int(n, 5, 1, 20)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_category(f"{name}-{i + 1}" if n > 1 else name)
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f"created {done}/{n} categories"))

    @commands.command(name="massrolecreate", brief="Create N roles in server")
    @commands.guild_only()
    async def massrolecreate(self, ctx, name: str = "Role", n: int = 5):
        n = _safe_int(n, 5, 1, 50)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_role(name=f"{name}-{i + 1}" if n > 1 else name)
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f"created {done}/{n} roles"))

    @commands.command(name="massvc", brief="Create N voice channels")
    @commands.guild_only()
    async def massvc(self, ctx, name: str = "VC", n: int = 5):
        n = _safe_int(n, 5, 1, 50)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_voice_channel(f"{name}-{i + 1}" if n > 1 else name)
                done += 1
            except Exception as e:
                if "429" in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f"created {done}/{n} VCs"))

    @commands.command(name="massreact", brief="React to last N messages with emoji")
    async def massreact(self, ctx, emoji: str = "", limit: int = 10):
        if not emoji:
            return await ctx.message.edit(content=S.ui_err("usage: massreact <emoji> [limit]"))
        limit = _safe_int(limit, 10, 1, 50)
        await ctx.message.delete()
        done = 0
        async for msg in ctx.channel.history(limit=limit):
            if self._abort.is_set():
                break
            try:
                await msg.add_reaction(emoji)
                done += 1
            except Exception:
                pass
            await asyncio.sleep(0.4)
        conf = await ctx.channel.send(S.ui_ok(f"reacted to {done}"))
        await asyncio.sleep(3)
        try:
            await conf.delete()
        except Exception:
            pass

    @commands.command(name="massdelete", brief="Delete your own last N messages")
    async def massdelete(self, ctx, n: int = 10):
        n = _safe_int(n, 10, 1, 200)
        await ctx.message.delete()
        deleted = 0
        async for msg in ctx.channel.history(limit=n * 3):
            if self._abort.is_set():
                break
            if msg.author.id == self.bot.user.id:
                try:
                    await msg.delete()
                    deleted += 1
                except Exception:
                    pass
                await asyncio.sleep(0.3)
                if deleted >= n:
                    break
        conf = await ctx.channel.send(S.ui_ok(f"deleted {deleted}"))
        await asyncio.sleep(3)
        try:
            await conf.delete()
        except Exception:
            pass

    async def _collect_dm_targets(self, scope: str = "dms"):
        """Return list of (label, channel_or_user_id, mode) for massdm.
        mode: 'channel' (existing DMChannel) or 'user' (need open via API).
        scope: dms | friends | both
        """
        scope = (scope or "dms").lower().strip()
        targets = []
        seen = set()

        if scope in ("dms", "dm", "all", "both", "everyone"):
            for ch in self.bot.private_channels:
                if not isinstance(ch, discord.DMChannel):
                    continue
                recip = getattr(ch, "recipient", None)
                uid = recip.id if recip else None
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                targets.append((str(recip) if recip else str(ch.id), ch, "channel"))

        if scope in ("friends", "friend", "both", "all"):
            friends = []
            try:
                rels = getattr(self.bot, "friends", None) or getattr(self.bot, "relationships", None)
                if rels is not None:
                    for r in list(rels):
                        try:
                            t = getattr(r, "type", None)
                            # type 1 = friend in discord.py-self
                            if t is not None and int(t) != 1:
                                continue
                            u = getattr(r, "user", None) or r
                            if u and getattr(u, "id", None):
                                friends.append(u)
                        except Exception:
                            pass
            except Exception:
                pass
            # fallback: relationships endpoint via http if empty
            if not friends:
                try:
                    import aiohttp
                    token = S.TOKEN or getattr(getattr(self.bot, "http", None), "token", "")
                    async with aiohttp.ClientSession() as s:
                        async with s.get(
                            "https://discord.com/api/v9/users/@me/relationships",
                            headers={"Authorization": token, "User-Agent": S.USER_AGENT},
                        ) as r:
                            if r.status == 200:
                                data = await r.json()
                                for item in data or []:
                                    if int(item.get("type", 0)) != 1:
                                        continue
                                    u = item.get("user") or {}
                                    uid = u.get("id")
                                    if uid:
                                        class _U:
                                            pass
                                        uu = _U()
                                        uu.id = int(uid)
                                        uu.name = u.get("username") or uid
                                        friends.append(uu)
                except Exception as e:
                    print(f"[massdm] friends fetch: {e}")

            for u in friends:
                uid = int(u.id)
                if uid in seen:
                    continue
                seen.add(uid)
                # prefer existing DM channel
                existing = None
                for ch in self.bot.private_channels:
                    if isinstance(ch, discord.DMChannel) and getattr(getattr(ch, "recipient", None), "id", None) == uid:
                        existing = ch
                        break
                if existing:
                    targets.append((str(getattr(u, "name", uid)), existing, "channel"))
                else:
                    targets.append((str(getattr(u, "name", uid)), uid, "user"))

        return targets

    async def _send_one_dm(self, target, text, session, headers):
        """Send one DM. target is (label, ch_or_uid, mode). Returns True on success."""
        label, obj, mode = target
        try:
            if mode == "channel":
                await obj.send(text)
                return True
            # open DM then send via API (faster, fewer library hops)
            uid = str(obj)
            async with session.post(
                "https://discord.com/api/v9/users/@me/channels",
                headers=headers,
                json={"recipient_id": uid},
            ) as r:
                if r.status == 429:
                    await on_rate_limit(4.0)
                    return False
                if r.status not in (200, 201):
                    return False
                data = await r.json()
                cid = data.get("id")
            if not cid:
                return False
            async with session.post(
                f"https://discord.com/api/v9/channels/{cid}/messages",
                headers=headers,
                json={"content": text},
            ) as r2:
                if r2.status == 429:
                    await on_rate_limit(4.0)
                    return False
                return r2.status in (200, 201)
        except Exception:
            return False

    async def _run_massdm(self, targets, text, status_msg, delay_s: float = 0.85):
        sent = failed = 0
        token = S.TOKEN or getattr(getattr(self.bot, "http", None), "token", "")
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": getattr(S, "USER_AGENT", "Mozilla/5.0"),
        }
        import aiohttp
        async with aiohttp.ClientSession() as session:
            for i, target in enumerate(targets):
                if self._abort.is_set():
                    break
                ok = await self._send_one_dm(target, text, session, headers)
                if ok:
                    sent += 1
                else:
                    failed += 1
                if status_msg and i % 3 == 0:
                    try:
                        await status_msg.edit(
                            content=S.ui_info(f"DMing… {sent}/{len(targets)}  fail {failed}")
                        )
                    except Exception:
                        pass
                # slightly fast with light jitter
                await delay(max(0.35, delay_s * 0.75), delay_s * 1.25)
        if status_msg:
            try:
                await status_msg.edit(
                    content=S.ui_ok(f"massdm done — sent {sent}/{len(targets)}  fail {failed}")
                )
            except Exception:
                pass

    @commands.command(name="massdm", brief="Mass DM — scope: dms | friends | both")
    async def massdm(self, ctx, scope: str = "dms", *, text: str = ""):
        """
        massdm <scope> <message>
        scope: dms (open DM list), friends, both
        example: massdm dms hello
                 massdm friends yo
                 massdm both promo text
        """
        scopes = {"dms", "dm", "friends", "friend", "both", "all", "everyone"}
        if scope.lower() not in scopes:
            # treat first token as part of message (legacy: massdm <message>)
            text = f"{scope} {text}".strip() if text else scope
            scope = "dms"
        if not text:
            return await ctx.message.edit(
                content=S.ui_err("usage: massdm [dms|friends|both] <message>")
            )
        if self._dm_task and not self._dm_task.done():
            return await ctx.message.edit(content=S.ui_err("massdm running — stopdm"))

        targets = await self._collect_dm_targets(scope)
        if not targets:
            return await ctx.message.edit(content=S.ui_err(f"no targets for scope `{scope}`"))

        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._reset_abort()
        status = await ctx.channel.send(
            S.ui_info(f"massdm `{scope}` → {len(targets)} targets (stopdm to abort)")
        )
        self._dm_task = asyncio.create_task(
            self._run_massdm(targets, text, status, delay_s=0.85)
        )

    @commands.command(name="massdmfast", brief="Faster massdm (shorter delay)")
    async def massdmfast(self, ctx, scope: str = "dms", *, text: str = ""):
        scopes = {"dms", "dm", "friends", "friend", "both", "all", "everyone"}
        if scope.lower() not in scopes:
            text = f"{scope} {text}".strip() if text else scope
            scope = "dms"
        if not text:
            return await ctx.message.edit(content=S.ui_err("usage: massdmfast [dms|friends|both] <msg>"))
        if self._dm_task and not self._dm_task.done():
            return await ctx.message.edit(content=S.ui_err("massdm running — stopdm"))
        targets = await self._collect_dm_targets(scope)
        if not targets:
            return await ctx.message.edit(content=S.ui_err(f"no targets for `{scope}`"))
        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._reset_abort()
        status = await ctx.channel.send(
            S.ui_info(f"massdmfast `{scope}` → {len(targets)} (stopdm to abort)")
        )
        self._dm_task = asyncio.create_task(
            self._run_massdm(targets, text, status, delay_s=0.45)
        )

    @commands.command(name="stopdm", brief="Stop running mass DM")
    async def stopdm(self, ctx):
        self._abort.set()
        if self._dm_task and not self._dm_task.done():
            self._dm_task.cancel()
            try:
                await self._dm_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dm_task = None
            await ctx.message.edit(content=S.ui_ok("massdm aborted"))
        else:
            await ctx.message.edit(content=S.ui_info("no massdm running"))

    @commands.command(name="stopmass", brief="Abort any running mass action")
    async def stopmass(self, ctx):
        self._abort.set()
        if self._dm_task and not self._dm_task.done():
            self._dm_task.cancel()
            try:
                await self._dm_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dm_task = None
        await ctx.message.edit(content=S.ui_ok("mass abort signal sent"))

    @commands.command(name="dmstats", brief="Show DM channel stats")
    async def dmstats(self, ctx):
        dms = [c for c in self.bot.private_channels if isinstance(c, discord.DMChannel)]
        friends_n = 0
        try:
            targets = await self._collect_dm_targets("friends")
            friends_n = len(targets)
        except Exception:
            pass
        await ctx.message.edit(content=S.ui_box("dm stats", [
            f"  {S.DIM}open DMs{S.RESET}  {len(dms)}",
            f"  {S.DIM}friends{S.RESET}   {friends_n}",
            f"  {S.DIM}massdm{S.RESET}    {'running' if self._dm_task and not self._dm_task.done() else 'idle'}",
        ]))

    @commands.command(name="massdmfile", brief="Mass DM IDs from file")
    async def massdmfile(self, ctx, filepath: str = "", *, text: str = ""):
        if not filepath or not text:
            return await ctx.message.edit(content=S.ui_err("usage: massdmfile <path> <msg>"))
        if not os.path.exists(filepath):
            return await ctx.message.edit(content=S.ui_err("file not found"))
        with open(filepath, encoding="utf-8") as f:
            ids = [l.strip() for l in f if l.strip().isdigit()]
        if not ids:
            return await ctx.message.edit(content=S.ui_err("no valid user ids in file"))
        await ctx.message.delete()
        self._reset_abort()
        h = {
            "Authorization": S.TOKEN,
            "Content-Type": "application/json",
            "User-Agent": S.USER_AGENT,
        }
        done = 0
        import aiohttp
        async with aiohttp.ClientSession() as s:
            for uid in ids:
                if self._abort.is_set():
                    break
                try:
                    async with s.post(
                        "https://discord.com/api/v9/users/@me/channels",
                        headers=h,
                        json={"recipient_id": uid},
                    ) as r:
                        if r.status == 200:
                            cid = (await r.json()).get("id")
                            if cid:
                                async with s.post(
                                    f"https://discord.com/api/v9/channels/{cid}/messages",
                                    headers=h,
                                    json={"content": text},
                                ) as r2:
                                    if r2.status in (200, 201):
                                        done += 1
                    if r.status == 429:
                        await on_rate_limit(5.0)
                except Exception:
                    pass
                await delay(0.5, 0.9)
        await ctx.channel.send(S.ui_ok(f"sent to {done}/{len(ids)}"))

    @commands.command(name="massfriend", brief="Mass add friends from ID file")
    async def massfriend(self, ctx, filepath: str = ""):
        if not filepath or not os.path.exists(filepath):
            return await ctx.message.edit(content=S.ui_err("usage: massfriend <file>"))
        with open(filepath, encoding="utf-8") as f:
            ids = [l.strip() for l in f if l.strip().isdigit()]
        if not ids:
            return await ctx.message.edit(content=S.ui_err("no valid user ids in file"))
        await ctx.message.delete()
        self._reset_abort()
        h = {
            "Authorization": S.TOKEN,
            "Content-Type": "application/json",
            "User-Agent": S.USER_AGENT,
        }
        done = 0
        import aiohttp
        async with aiohttp.ClientSession() as s:
            for uid in ids:
                if self._abort.is_set():
                    break
                try:
                    async with s.put(
                        f"https://discord.com/api/v9/users/@me/relationships/{uid}",
                        headers=h,
                        json={"type": 1},
                    ) as r:
                        if r.status in (200, 201, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.5)
        await ctx.channel.send(S.ui_ok(f"sent {done}/{len(ids)}"))

    @commands.command(name="massjoin", brief="Join server with hosted tokens")
    async def massjoin(self, ctx, invite: str = "", count: int = 1):
        from uuid import uuid4
        import aiohttp
        if not invite:
            return await ctx.message.edit(content=S.ui_err("usage: massjoin <invite> [count]"))
        invite = (
            invite.replace("https://discord.gg/", "")
            .replace("http://discord.gg/", "")
            .replace("discord.gg/", "")
            .replace("https://discord.com/invite/", "")
            .strip("/")
        )
        tokens = list(getattr(S, "HOSTED_TOKENS", []) or [])[: _safe_int(count, 1, 1, 50)]
        if not tokens:
            return await ctx.message.edit(content=S.ui_err("no hosted tokens in S.HOSTED_TOKENS"))
        await ctx.message.delete()
        self._reset_abort()
        done = 0
        async with aiohttp.ClientSession() as s:
            for tk in tokens:
                if self._abort.is_set():
                    break
                try:
                    async with s.post(
                        f"https://discord.com/api/v9/invites/{invite}",
                        headers={
                            "Authorization": tk,
                            "Content-Type": "application/json",
                            "User-Agent": S.USER_AGENT,
                        },
                        json={"session_id": str(uuid4())[:12]},
                    ) as r:
                        if r.status in (200, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.5)
        await ctx.channel.send(S.ui_ok(f"joined {done}/{len(tokens)}"))

    @commands.command(name="massleave", brief="Leave a server with all hosted tokens")
    async def massleave(self, ctx, guild_id: str = ""):
        import aiohttp
        if not guild_id:
            return await ctx.message.edit(content=S.ui_err("usage: massleave <guild_id>"))
        tokens = list(getattr(S, "HOSTED_TOKENS", []) or [])
        if not tokens:
            return await ctx.message.edit(content=S.ui_err("no hosted tokens"))
        await ctx.message.delete()
        self._reset_abort()
        done = 0
        async with aiohttp.ClientSession() as s:
            for tk in tokens:
                if self._abort.is_set():
                    break
                try:
                    async with s.delete(
                        f"https://discord.com/api/v9/users/@me/guilds/{guild_id}",
                        headers={"Authorization": tk, "User-Agent": S.USER_AGENT},
                    ) as r:
                        if r.status in (200, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.0)
        await ctx.channel.send(S.ui_ok(f"left {done}/{len(tokens)}"))


    @commands.command(name="massreport", brief="Mass report users from mentions or ID file")
    async def massreport(self, ctx, reason: str = "spam", *, targets: str = ""):
        """
        massreport <reason> <@users...>
        massreport <reason> file:<path>
        reasons: spam | illegal | harassment | malware | other
        """
        reason_map = {
            "spam": 1,
            "illegal": 3,
            "harassment": 4,
            "malware": 5,
            "other": 1,
        }
        key = (reason or "spam").lower()
        reason_type = reason_map.get(key, 1)

        user_ids = []
        if targets.startswith("file:"):
            path = targets[5:].strip()
            if not os.path.exists(path):
                return await ctx.message.edit(content=S.ui_err("file not found"))
            with open(path, encoding="utf-8") as f:
                user_ids = [l.strip() for l in f if l.strip().isdigit()]
        else:
            for m in ctx.message.mentions:
                user_ids.append(str(m.id))
            for tok in (targets or "").split():
                tok = tok.strip("<@!>")
                if tok.isdigit():
                    user_ids.append(tok)
        user_ids = list(dict.fromkeys(user_ids))
        if not user_ids:
            return await ctx.message.edit(
                content=S.ui_err("usage: massreport <reason> <@users|file:path>")
            )

        token = S.TOKEN or getattr(getattr(self.bot, "http", None), "token", "")
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": getattr(S, "USER_AGENT", "Mozilla/5.0"),
        }
        done = 0
        import aiohttp
        await ctx.message.edit(content=S.ui_info(f"reporting {len(user_ids)}..."))
        self._reset_abort()
        async with aiohttp.ClientSession() as s:
            for uid in user_ids:
                if self._abort.is_set():
                    break
                try:
                    async with s.post(
                        f"https://discord.com/api/v9/users/{uid}/report",
                        headers=headers,
                        json={"reason": reason_type, "version": "1.0"},
                    ) as r:
                        if r.status in (200, 201, 204):
                            done += 1
                        elif r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await delay(0.6, 1.1)
        await ctx.message.edit(content=S.ui_ok(f"reported {done}/{len(user_ids)} ({key})"))


async def setup(bot):
    await bot.add_cog(MassCog(bot))
