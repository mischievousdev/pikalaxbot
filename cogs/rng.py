import random

from discord.ext import commands

from cogs import BaseCog


class DiceRollConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower()
        count, sides = argument.split('d')
        if not (count or sides):
            raise ValueError
        count = int(count) if count else 1
        sides = int(sides) if sides else 6
        assert 1 <= count <= 200 and 2 <= sides <= 100
        return count, sides


class Rng(BaseCog):
    @commands.command()
    async def choose(self, ctx: commands.Context, *args):
        """Choose between multiple options separated by spaces.
        Use quotes to wrap multi-word options."""
        await ctx.send(random.choice(args))

    @commands.command()
    async def roll(self, ctx, params: DiceRollConverter = (1, 6)):
        """Roll one or more dice with a given number of sides."""
        count, sides = params
        rolls = [str(random.randint(1, sides)) for i in range(count)]
        rollstr = ', '.join(rolls)
        dice = 'die' if count == 1 else 'dice'
        await ctx.send(f'Rolled {count} {sides}-sided {dice}.  Result:\n'
                       f'{rollstr}')

    @commands.command(name='someone')
    @commands.is_owner()
    async def ping_random(self, ctx: commands.Context):
        """Ping a random person in the channel."""
        await ctx.send(random.choice(ctx.channel.members).mention)

    async def __error(self, ctx, exc):
        if isinstance(exc, commands.ConversionError):
            orig = exc.original
            if isinstance(orig, AssertionError):
                await ctx.send(f'Argument to {ctx.prefix}{ctx.command} must not be more than 200 dice, '
                               f'and each die must have between 2 and 100 sides.')
                exc = None
            elif isinstance(orig, ValueError):
                await ctx.send(f'Argument to {ctx.prefix}{ctx.command} must be of the form [N]d[S], '
                               f'where N is the number of dice and S is the number of sides per die. '
                               f'Both N and S are optional, but at least one must be supplied.')
                exc = None
            elif orig is not None:
                exc = orig
        if exc is not None:
            await ctx.send(f'**{exc.__class__.__name__}:** {exc} {self.bot.command_error_emoji}',
                           delete_after=10)
        self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(Rng(bot))