"""Discord bot bridge — replies with the locally loaded model.

Runs discord.py inside a dedicated thread/event loop so the Tk UI stays
responsive. The bot answers messages that start with the configured prefix
(or that mention it), using a ``handler(text) -> str`` callback supplied by
the app (which serialises on the engine lock shared with the UI).
"""

import asyncio
import threading


def _split(text, limit=1900):
    """Split a long reply into Discord-safe chunks, preferring newlines."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current)
    return chunks


class DiscordBot:
    def __init__(self, token, prefix="!", channel_id="", handler=None,
                 on_status=None):
        self.token = token
        self.prefix = prefix or "!"
        self.channel_id = str(channel_id or "")
        self.handler = handler or (lambda t: "No handler.")
        self.on_status = on_status or (lambda s: None)
        self._bot = None
        self._loop = None
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        try:
            import discord  # noqa: F401
        except ImportError:
            raise RuntimeError("discord.py is not available in this build.")
        if self.running:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._bot and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self._bot.close(), self._loop)
            except RuntimeError:
                pass
        self._thread = None

    def _run(self):
        import discord

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        intents = discord.Intents.default()
        intents.message_content = True
        bot = discord.Client(intents=intents)
        self._bot = bot

        @bot.event
        async def on_ready():
            self.on_status(f"Online as {bot.user}")

        @bot.event
        async def on_message(message):
            if message.author == bot.user:
                return
            if self.channel_id and str(message.channel.id) != self.channel_id:
                return
            content = message.content or ""
            prompt = None
            if content.startswith(self.prefix):
                prompt = content[len(self.prefix):].strip()
            elif bot.user in message.mentions:
                prompt = content.replace(f"<@{bot.user.id}>", "").strip()
            if not prompt:
                return
            try:
                answer = await asyncio.to_thread(self.handler, prompt)
            except Exception as exc:
                answer = f"Error: {exc}"
            for chunk in _split(answer or "(no reply)"):
                try:
                    await message.reply(chunk)
                except Exception:
                    break

        try:
            self._loop.run_until_complete(bot.start(self.token))
        except Exception as exc:
            self.on_status(f"Discord error: {exc}")
        finally:
            self._bot = None