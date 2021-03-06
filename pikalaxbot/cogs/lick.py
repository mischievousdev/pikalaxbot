import random
import discord
from discord.ext import commands
from . import BaseCog
import re


class Lick(BaseCog):
    notes_s = 'C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'
    notes_f = 'C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'
    lick = 0, 2, 3, 5, 2, -2, 0

    @commands.command(name='lick')
    async def lick_c(self, ctx: commands.Context):
        """
        https://m.youtube.com/watch?v=krDxhnaKD7Q
        """
        start = random.randint(0, 11)
        use_s = True
        for i, tongue in enumerate(self.lick[:-1]):
            if self.notes_s[(tongue + start) % 12][0] == self.notes_s[(self.lick[i + 1] + start) % 12][0]:
                use_s = False
                break
        await ctx.send(' '.join((self.notes_s if use_s else self.notes_f)[(start + offset) % 12] for offset in self.lick))

    @lick_c.error
    async def lick_error(self, ctx: commands.Context, exc: Exception):
        await ctx.send(f'**{exc.__class__.__name__}**: {exc}')
    
    @commands.command(name='licc')
    async def licc_c(self, ctx: commands.Context, *, recipient: discord.Member = None):
        """
        liccs u
        """
        emotes = [emote for emote in ctx.bot.emojis if re.search(r'lic[ck]', emote.name, re.I) is not None]
        emote = random.choice(emotes)
        if recipient:
            await ctx.send(f'{ctx.author.display_name} gave {recipient.mention} a huge licc {emote}')
        else:
            await ctx.send(f'{emote}')


def setup(bot):
    bot.add_cog(Lick(bot))
