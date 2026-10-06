import asyncio
import discord
from discord.ext import commands
from . import state as S

try:
    from . import spoofer as SP
except Exception:
    SP = None

_satellite_bots: list = []


class MultiSpoofCog(commands.Cog, name="multispoof"):
    """Multi-device spoof pool. Devices only apply on IDENTIFY, so each switch reconnects."""

    def __init__(self, bot):
        self.bot = bot
        self._rotate_task = None
        self._pool: list = []
        self._mode = "rotate"
        self._interval = 120.0
        self._cursor = 0
        self._busy = False

    def _valid_platforms(self):
        if SP is None:
            return {}
        return getattr(SP, "PLATFORM_PRESETS", {}) or {}

    def _stop_rotate(self):
        t = self._rotate_task
        if t and not t.done():
            t.cancel()
        self._rotate_task = None

    async def _apply_key(self, key: str, *, reconnect: bool = False) -> str:
        """
        Push platform into spoofer pool.
        reconnect=True only for one-shot sticky (still risky — Discord may invalidate).
        Rotate never reconnects; it only updates the pool so the *next natural*
        identify (login / network blip) picks the device. Safe for the token.
        """
        presets = self._valid_platforms()
        preset = presets.get(key)
        if not preset:
            return f"unknown:{key}"
        if SP is None:
            return "spoofer missing"

        SP._set_pool([key])
        SP._POOL["mode"] = "sticky"
        SP._POOL["cursor"] = 0
        try:
            SP._patch_http(self.bot, preset)
        except Exception as e:
            print(f"[multispoof] http patch: {e}")

        SP._POOL["last"] = preset  # soft-mark as active selection

        if not reconnect:
            return preset.get("label", key) + " (soft — next login applies device)"

        # One-shot sticky only — single reconnect + optional force identify
        cog = self.bot.get_cog("spoofer")
        if cog is None:
            return preset.get("label", key)
        try:
            if hasattr(cog, "_reconnect"):
                await cog._reconnect()
            await asyncio.sleep(2)
            if hasattr(cog, "_force_identify"):
                await cog._force_identify(preset)
        except Exception as e:
            print(f"[multispoof] reconnect/identify: {e}")
            return f"err:{e}"
        last = SP._POOL.get("last") or preset
        return last.get("label", key)

    async def _rotate_loop(self):
        while True:
            try:
                if not self._pool:
                    await asyncio.sleep(5)
                    continue
                if self._busy:
                    await asyncio.sleep(2)
                    continue
                key = self._pool[self._cursor % len(self._pool)]
                self._cursor += 1
                self._busy = True
                try:
                    label = await self._apply_key(key, reconnect=False)
                    print(f"[multispoof] rotate → {label}")
                finally:
                    self._busy = False
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._busy = False
                print(f"[multispoof] rotate err: {e}")
                await asyncio.sleep(5)

    @commands.command(name="multispoof", aliases=["mspoof"], brief="Multi-device spoof pool")
    async def multispoof(self, ctx, sub: str = "status", *platforms):
        """
        multispoof status
        multispoof list
        multispoof set desktop mobile xbox
        multispoof add ios
        multispoof remove xbox
        multispoof rotate [seconds]
        multispoof sticky <platform>
        multispoof next
        multispoof stop
        multispoof start
        """
        sub = (sub or "status").lower()
        presets = self._valid_platforms()

        if sub in ("status", "info"):
            last = None
            try:
                last = (SP._POOL.get("last") or {}) if SP else {}
            except Exception:
                last = {}
            rows = [
                f"  {S.DIM}mode{S.RESET}      {self._mode}",
                f"  {S.DIM}pool{S.RESET}      {', '.join(self._pool) or '(empty)'}",
                f"  {S.DIM}interval{S.RESET}  {self._interval:.0f}s",
                f"  {S.DIM}rotating{S.RESET}  {bool(self._rotate_task and not self._rotate_task.done())}",
                f"  {S.DIM}last{S.RESET}      {(last or {}).get('label', 'none')}",
                f"  {S.DIM}device{S.RESET}    {(last or {}).get('device', '') or 'none'}",
            ]
            return await ctx.message.edit(content=S.ui_box("multispoof", rows))

        if sub == "list":
            rows = [f"  {S.GREY}•{S.RESET} {k:<12} {v.get('label', k)}" for k, v in presets.items()]
            return await ctx.message.edit(
                content=S._paginate("platforms", f"{len(presets)} available", rows) if rows else S.ui_info("none")
            )

        if sub in ("set", "pool"):
            keys = [p.lower() for p in platforms if p.lower() in presets]
            if not keys:
                return await ctx.message.edit(
                    content=S.ui_err(f"usage: multispoof set <p1> <p2> ...\nvalid: {', '.join(presets)}")
                )
            self._pool = keys
            self._cursor = 0
            try:
                SP._set_pool(keys)
                SP._POOL["mode"] = "rotate"
            except Exception:
                pass
            return await ctx.message.edit(content=S.ui_ok(f"pool → {', '.join(keys)}"))

        if sub == "add":
            added = []
            for p in platforms:
                k = p.lower()
                if k in presets and k not in self._pool:
                    self._pool.append(k)
                    added.append(k)
            if not added:
                return await ctx.message.edit(content=S.ui_err("nothing added — multispoof list"))
            try:
                SP._set_pool(self._pool)
            except Exception:
                pass
            return await ctx.message.edit(content=S.ui_ok(f"added {', '.join(added)}"))

        if sub in ("remove", "rm", "del"):
            removed = []
            for p in platforms:
                k = p.lower()
                if k in self._pool:
                    self._pool.remove(k)
                    removed.append(k)
            try:
                SP._set_pool(self._pool)
            except Exception:
                pass
            return await ctx.message.edit(content=S.ui_ok(f"removed {', '.join(removed) or 'none'}"))

        if sub == "rotate":
            if platforms:
                try:
                    self._interval = max(20.0, float(platforms[0]))
                except Exception:
                    pass
            if not self._pool:
                return await ctx.message.edit(content=S.ui_err("pool empty — multispoof set desktop mobile ..."))
            self._mode = "rotate"
            self._stop_rotate()
            self._rotate_task = asyncio.create_task(self._rotate_loop())
            # apply first device immediately so something shows now
            first = self._pool[0]
            await ctx.message.edit(content=S.ui_info(f"applying {first} then rotating every {self._interval:.0f}s…"))
            label = await self._apply_key(first, reconnect=False)
            self._cursor = 1
            return await ctx.channel.send(S.ui_ok(f"multispoof → {label}  pool: {', '.join(self._pool)}"))

        if sub == "sticky":
            if not platforms:
                return await ctx.message.edit(content=S.ui_err("usage: multispoof sticky <platform>"))
            key = platforms[0].lower()
            if key not in presets:
                return await ctx.message.edit(content=S.ui_err(f"unknown platform: {key}"))
            self._mode = "sticky"
            self._stop_rotate()
            await ctx.message.edit(content=S.ui_info(f"spoofing → {key} (reconnecting…)"))
            label = await self._apply_key(key, reconnect=False)
            return await ctx.channel.send(S.ui_ok(f"sticky → {label}"))

        if sub == "next":
            if not self._pool:
                return await ctx.message.edit(content=S.ui_err("pool empty"))
            key = self._pool[self._cursor % len(self._pool)]
            self._cursor += 1
            await ctx.message.edit(content=S.ui_info(f"switching → {key}"))
            label = await self._apply_key(key, reconnect=False)
            return await ctx.channel.send(S.ui_ok(f"now → {label}"))

        if sub == "stop":
            self._stop_rotate()
            for b in list(_satellite_bots):
                try:
                    await b.close()
                except Exception:
                    pass
            _satellite_bots.clear()
            return await ctx.message.edit(content=S.ui_ok("multispoof stopped"))

        if sub == "start":
            if not self._pool:
                return await ctx.message.edit(content=S.ui_err("set a pool first: multispoof set desktop mobile"))
            self._mode = "rotate"
            self._stop_rotate()
            self._rotate_task = asyncio.create_task(self._rotate_loop())
            await ctx.message.edit(content=S.ui_info("starting rotate…"))
            label = await self._apply_key(self._pool[0], reconnect=False)
            self._cursor = 1
            return await ctx.channel.send(S.ui_ok(f"started → {label}"))

        return await ctx.message.edit(
            content=S.ui_err("subs: status | list | set | add | remove | rotate | sticky | next | start | stop")
        )


async def setup(bot):
    await bot.add_cog(MultiSpoofCog(bot))
