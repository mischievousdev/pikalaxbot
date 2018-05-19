import asyncio
import discord
import json
from discord.ext import commands
from discord import compat
from discord.client import log
from utils import markov, sql
import random
import logging
import sys
import time
import traceback


initial_extensions = (
    'cogs.meme',
    'cogs.hangman',
    'cogs.anagram',
    'cogs.trashcans',
    'cogs.leaderboard',
)


def log_exc(exc):
    log.error(traceback.format_exception(type(exc), exc, exc.__traceback__))


class PikalaxBOT(commands.Bot):
    def __init__(self, settings):
        meta = settings.get('meta', {})
        credentials = settings.get('credentials', {})
        user = settings.get('user', {})

        self.owner_id = credentials.get('owner')

        self.whitelist = {}
        self.debug = False
        self.markov_channels = []
        self.cooldown = 10
        self.initialized = False

        for key, value in user.items():
            setattr(self, key, value)

        self.chains = {chan: None for chan in self.markov_channels}

        self._token = credentials.get('token')
        command_prefix = meta.get('prefix', '!')

        self.storedMsgsSet = set()

        super().__init__(command_prefix)

    def run(self):
        super().run(self._token)

    def print(self, message):
        if self.debug:
            print(message)

    def _do_cleanup(self):
        loop = self.loop

        if loop.is_closed():
            return

        for channel in self.whitelist.values():
            compat.create_task(channel.send('Shutting down... (console kill)'), loop=loop)

        if not loop.is_running():
            loop.run_forever()

        super()._do_cleanup()

    def gen_msg(self, ch, len_max=64, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self.chains.get(ch)
        if chain is None:
            return
        for i in range(n_attempts):
            l = chain.generate(len_max)
            if len(l) > lng_cnt:
                msg = str.join(' ', l)
                if i == 0 or msg not in self.storedMsgsSet:
                    lng_cnt = len(l)
                    longest = str.join(' ', l)
                    if lng_cnt == len_max:
                        break
        return longest

    async def on_command_error(self, context, exception):
        if not self.debug and isinstance(exception, commands.CommandError):
            await super().on_command_error(context, exception)
        else:
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            log.error(tb[0])


if __name__ == '__main__':
    sql.db_init()
    handler = logging.StreamHandler(stream=sys.stderr)
    fmt = logging.Formatter()
    handler.setFormatter(fmt)
    log.addHandler(handler)
    with open('settings.json') as fp:
        settings = json.load(fp)
    bot = PikalaxBOT(settings)
    log.setLevel(logging.INFO)
    for extn in initial_extensions:
        bot.load_extension(extn)
    help_bak = bot.remove_command('help')
    help_bak.name = 'pikahelp'
    bot.add_command(help_bak)


    @bot.check
    def is_allowed(ctx: commands.Context):
        return ctx.channel.id in ctx.bot.whitelist and not ctx.author.bot


    @bot.check
    def is_not_me(ctx: commands.Context):
        return ctx.author != ctx.bot.user


    @bot.event
    async def on_ready():
        for ch in list(bot.chains.keys()):
            if bot.chains[ch] is not None:
                del bot.chains[ch]
            bot.chains[ch] = markov.Chain(store_lowercase=True)
            channel = bot.get_channel(ch)  # type: discord.TextChannel
            try:
                async for msg in channel.history(limit=5000):
                    learn_markov(msg, force=True)
                log.info(f'Initialized channel {channel.name}')
            except discord.Forbidden:
                bot.chains.pop(ch)
                log.error(f'Failed to get message history from {channel.name} (403 FORBIDDEN)')
            except AttributeError:
                bot.chains.pop(ch)
                log.error(f'Failed to load chain {ch:d}')
        bot.whitelist = {ch.id: ch for ch in map(bot.get_channel, bot.whitelist) if ch is not None}
        bot.initialized = True
        activity = discord.Game('!pikahelp')
        await bot.change_presence(activity=activity)
        for channel in bot.whitelist.values():
            await channel.send('_is active and ready for abuse!_')


    @bot.check
    def is_initialized(ctx):
        return ctx.bot.initialized


    def markov_general_checks(msg):
        if not bot.initialized:
            return False
        if msg.channel.id not in bot.whitelist:
            return False
        if msg.author.bot:
            return False
        if len(bot.chains) == 0:
            return False
        return True


    def can_markov(msg):
        if not markov_general_checks(msg):
            return False
        if bot.user.mentioned_in(msg):
            return True
        if bot.user.name.lower() in msg.clean_content.lower():
            return True
        if bot.user.display_name.lower() in msg.clean_content.lower():
            return True
        return False


    def can_learn_markov(msg, force=False):
        if not (force or markov_general_checks(msg)):
            return False
        if msg.author.bot:
            return False
        return msg.channel.id in bot.chains and not msg.clean_content.startswith(bot.command_prefix)


    @bot.listen('on_message')
    async def send_markov(msg: discord.Message):
        if can_markov(msg):
            ch = random.choice(list(bot.chains.keys()))
            chain = bot.gen_msg(ch, len_max=250, n_attempts=10)
            await msg.channel.send(f'{msg.author.mention}: {chain}')


    def learn_markov(msg, force=False):
        if can_learn_markov(msg, force=force):
            bot.storedMsgsSet.add(msg.clean_content)
            bot.chains[msg.channel.id].learn_str(msg.clean_content)


    def forget_markov(msg, force=False):
        if can_learn_markov(msg, force=force):
            bot.chains[msg.channel.id].unlearn_str(msg.clean_content)


    @bot.listen('on_message')
    async def coro_learn_markov(msg):
        learn_markov(msg)


    @bot.listen('on_message_edit')
    async def coro_update_markov(old, new):
        forget_markov(old)
        learn_markov(new)


    @bot.listen('on_message_delete')
    async def coro_delete_markov(msg):
        forget_markov(msg)


    async def ctx_is_owner(ctx):
        return await ctx.bot.is_owner(ctx.author)


    @bot.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikakill(ctx: commands.Context):
        await ctx.send('Shutting down...')
        await bot.close()


    log.info('Starting bot')
    bot.run()
