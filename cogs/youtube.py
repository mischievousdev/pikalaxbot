import asyncio
import discord
import youtube_dl
import ctypes.util
from discord.ext import commands
from utils.botclass import PikalaxBOT, VoiceCommandError
from utils.default_cog import Cog
from utils.converters import EspeakKwargsConverter
import subprocess
import os
import time
import re
from concurrent.futures import ThreadPoolExecutor


class cleaner_content(commands.clean_content):
    async def convert(self, ctx, argument):
        argument = await super().convert(ctx, argument)
        argument = re.sub(r'<a?:(\w+):\d+>', '\\1', argument)
        return argument


def connected_and_not_playing(ctx):
    return ctx.voice_client.is_connected() and not ctx.voice_client.is_playing()


class EspeakAudioSource(discord.FFmpegPCMAudio):
    @staticmethod
    def call_espeak(msg, fname, **kwargs):
        args = ['espeak', '-w', fname]
        for flag, value in kwargs.items():
            args.extend([f'-{flag}', str(value)])
        args.append(msg)
        subprocess.check_call(args)

    def __init__(self, cog, msg, *args, **kwargs):
        self.fname = f'tmp_{time.time()}.wav'
        self.call_espeak(msg, self.fname, **cog.espeak_kw)
        super().__init__(self.fname, *args, **kwargs)

    def cleanup(self):
        super().cleanup()
        if os.path.exists(self.fname):
            os.remove(self.fname)


class YouTube(Cog):
    __ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
    }
    __ffmpeg_options = {
        'before_options': '-nostdin -loglevel quiet',
        'options': '-vn'
    }
    espeak_kw = {}
    voice_chans = {}
    config_attrs = 'espeak_kw', 'voice_chans'
    __local_check = lambda self, ctx: self.ready

    def load_opus(self):
        if not discord.opus.is_loaded():
            opus_name = ctypes.util.find_library('libopus')
            if opus_name is None:
                self.bot.logger.error('Failed to find the Opus library.')
            else:
                discord.opus.load_opus(opus_name)
        return discord.opus.is_loaded()

    def __init__(self, bot: PikalaxBOT):
        super().__init__(bot)
        self.ready = False
        self.connections = {}

        with open(os.devnull, 'w') as DEVNULL:
            for executable in ('ffmpeg', 'avconv'):
                try:
                    subprocess.check_call([executable, '-h'], stdout=DEVNULL, stderr=DEVNULL)
                except FileNotFoundError:
                    continue
                self.ffmpeg = executable
                self.__ffmpeg_options['executable'] = executable
                break
            else:
                raise discord.ClientException('ffmpeg or avconv not installed')

        self.executor = ThreadPoolExecutor()
        self.__ytdl_player = youtube_dl.YoutubeDL(self.__ytdl_format_options)

    async def on_ready(self):
        if self.load_opus():
            self.bot.logger.info('Loaded opus')
            await self.fetch()
            for guild, chan in self.voice_chans.items():
                ch = self.bot.get_channel(chan)
                if isinstance(ch, discord.VoiceChannel):
                    try:
                        await ch.connect()
                    except asyncio.TimeoutError:
                        self.bot.logger.error('Failed to connect to voice channel %s (connection timed out)', ch.name)
                    except discord.ClientException:
                        self.bot.logger.error('Failed to connect to voice channel %s (duplicate connection)', ch.name)
                    else:
                        self.bot.logger.info('Connected to voice channel %s', ch.name)

            self.ready = True

    @commands.group()
    # @commands.is_owner()
    async def pikavoice(self, ctx: commands.Context):
        """Commands for interacting with the bot in voice channels"""
        if ctx.invoked_subcommand is None:
            raise commands.CommandInvokeError('Invalid subcommand')

    @pikavoice.command()
    @commands.is_owner()
    async def chan(self, ctx: commands.Context, ch: discord.VoiceChannel):
        """Join a voice channel on the current server."""

        # All errors shall be communicated to the user, and also
        # passed to the bot's on_command_error handler.
        async with ctx.channel.typing():
            if ch is None:
                raise VoiceCommandError('Channel not found')
            if not ctx.me.permissions_in(ch).connect:
                raise commands.MissingPermissions(['connect'])
            if ch.guild != ctx.guild:
                raise VoiceCommandError('Guild mismatch')
            if ctx.guild.id in self.voice_chans:
                if ch.id == self.voice_chans[ctx.guild.id]:
                    raise VoiceCommandError('Already connected to that channel')
                vcl: discord.VoiceClient = ctx.guild.voice_client
                if vcl is None:
                    raise VoiceCommandError('Guild does not support voice connections')
                if vcl.is_connected():
                    await vcl.move_to(ch)
                else:
                    await ch.connect()
            else:
                await ch.connect()
            self.voice_chans[ctx.guild.id] = ch.id
            await self.commit()
            await ctx.send('Joined the voice channel!')

    @pikavoice.command()
    @commands.check(connected_and_not_playing)
    async def say(self, ctx: commands.Context, *, msg: cleaner_content(fix_channel_mentions=True,
                                                                       escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        ctx.guild.voice_client.play(EspeakAudioSource(self, msg, executable=self.ffmpeg,
                                                      before_options='-loglevel quiet'),
                                    after=lambda e: print('Player error: %s' % e) if e else None)

    @commands.command()
    async def pikasay(self, ctx, *, msg: cleaner_content(fix_channel_mentions=True,
                                                         escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        await ctx.invoke(self.say, msg=msg)

    @pikavoice.command()
    async def stop(self, ctx: commands.Context):
        """Stop all playing audio"""
        vclient: discord.VoiceClient = ctx.guild.voice_client
        if vclient.is_playing():
            vclient.stop()

    @commands.command()
    async def pikashutup(self, ctx):
        """Stop all playing audio"""
        await ctx.invoke(self.stop)

    @pikavoice.command()
    async def params(self, ctx, *, kwargs: EspeakKwargsConverter):
        f"""Update pikavoice params.

        Syntax:
        {self.bot.command_prefix}pikavoice params a=amplitude
        g=gap k=emphasis p=pitch s=speed v=voice"""
        params = dict(self.espeak_kw)
        params.update(kwargs)
        try:
            EspeakAudioSource.call_espeak('Test', 'tmp.wav', **params)
        except subprocess.CalledProcessError:
            await ctx.send('Parameters could not be updated')
        else:
            self.espeak_kw = params
            await self.commit()
            await ctx.send('Parameters successfully updated')
        finally:
            os.remove('tmp.wav')

    @commands.command()
    async def pikaparams(self, ctx, *, kwargs):
        f"""Update pikavoice params.

        Syntax:
        {self.bot.command_prefix}pikaparams a=amplitude
        g=gap k=emphasis p=pitch s=speed v=voice"""
        await ctx.invoke(self.params, kwargs=kwargs)

    @commands.command()
    @commands.check(connected_and_not_playing)
    async def ytplay(self, ctx: commands.Context, url):
        ...


def setup(bot: PikalaxBOT):
    bot.add_cog(YouTube(bot))


def teardown(bot: PikalaxBOT):
    for vc in bot.voice_clients:  # type: discord.VoiceClient
        bot.loop.create_task(vc.disconnect())