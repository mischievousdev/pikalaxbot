# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Credits to Tustin2121, who wrote the original Puppy Kicker for Q20PokemonBot

import json
import datetime
import discord
from discord.ext import commands
import random
import os
from . import BaseCog
import typing
import collections
import string


class PuppyWars(BaseCog):
    DEADINSKY = 120002774653075457
    CHANCE_SHOWDOWN = 0.10
    CHANCE_PUPNADO = 0.03
    CHANCE_DOZEN = 0.02
    CHANCE_PUPWIN = 0.30
    CHANCE_URANIUM = 0.005
    NAME_URANIUM = "Kikatanium"
    ONLINE_STATES = discord.Status.online, discord.Status.idle
    COOLDOWN = collections.defaultdict(lambda: commands.Cooldown(1, 600, commands.BucketType.guild))

    def __init__(self, bot):
        super().__init__(bot)
        self.did_showdown: bool = False
        self.last: typing.Optional[datetime.datetime] = None

        dname = os.path.abspath(f'{os.path.dirname(__file__)}/../data')
        with open(os.path.join(dname, 'puppy.json')) as fp:
            self.dndstyle: typing.List[dict] = json.load(fp)

    async def init_db(self, sql):
        await sql.execute("create table if not exists puppy (sentinel integer primary key, uranium integer default 0, score_puppy integer default 0, score_dead integer default 0)")
        await sql.execute("replace into puppy(sentinel) values (66)")

    def deadinsky(self, ctx: commands.Context) -> typing.Union[discord.Member, discord.User]:
        return ctx.guild.get_member(PuppyWars.DEADINSKY) or self.bot.get_user(PuppyWars.DEADINSKY)

    @staticmethod
    def get_result(
            score: int,
            win_score: int = 0,
            lose_score: int = 0,
            payoff: typing.Dict[str, str] = {}
    ) -> (int, int, str):
        checks: typing.List[typing.Callable[[int], bool]] = [
            lambda s: s >= 3,
            lambda s: 0 < s < 3,
            lambda s: s == 0,
            lambda s: -3 < s < 0,
            lambda s: s <= -3
        ]
        differentials: typing.List[int] = [
            2 * win_score,
            win_score,
            lose_score,
            lose_score,
            0
        ]

        for i, f in enumerate(checks):
            if f(score):
                break
        else:
            raise ValueError('something went horribly wrong')
        dead_score: int = differentials[i]
        puppy_score: int = differentials[4 - i]
        return dead_score, puppy_score, payoff[str(2 - i)]

    def do_showdown(self, forced: int = None) -> (int, int, str):
        if forced is not None:
            showdown = self.dndstyle[forced]
        else:
            showdown = random.choice(self.dndstyle)

        # 0 = dead, 1 = puppy
        successes = [0, 0]
        pool = [5, 5]
        dice = [[], []]

        for i in range(2):
            while len(dice[i]) < pool[i]:
                rval = random.randint(1, 6)
                if rval >= 4:
                    successes[i] += 1
                if rval == 6:
                    pool[i] += 1
                dice[i].append(str(rval))
        differential = successes[0] - successes[1]
        dead_score, puppy_score, payoff = PuppyWars.get_result(differential, **showdown)
        setup_text = showdown['setup']
        dead_rolls = ' '.join(dice[0])
        puppy_rolls = ' '.join(dice[1])
        dead_crit = ' **[CRIT]**' if differential >= 3 else ''
        puppy_crit = ' **[CRIT]**' if differential <= -3 else ''
        rolloff = f'Roll off: ' \
                  f'{{deadinsky}} [{dead_rolls}] = {successes[0]} Successes{dead_crit} ' \
                  f'VS Puppies [{puppy_rolls}] = {successes[1]} Successes{puppy_crit}'
        return dead_score, puppy_score, f'{setup_text}\n{rolloff}\n{payoff}'

    async def do_kick(self, ctx: commands.Context) -> str:
        self.did_showdown = False
        deadinsky = self.deadinsky(ctx)
        async with self.bot.sql as sql:
            # Uranium
            if ctx.command.name == 'pkick' and ctx.author == deadinsky and random.random() < self.CHANCE_URANIUM:
                await sql.puppy_add_uranium(1)
                return f'{deadinsky.display_name} finds some {self.NAME_URANIUM} lying on the ground, ' \
                       f'and pockets it.'

            # Rolloff
            dead_is_here = isinstance(deadinsky, discord.Member) and deadinsky.status == discord.Status.online
            if dead_is_here and random.random() < self.CHANCE_SHOWDOWN:
                deaddelta, pupdelta, content = self.do_showdown()
                await sql.update_dead_score(deaddelta)
                await sql.update_puppy_score(pupdelta)
                self.did_showdown = True
                return content.format(deadinsky=deadinsky.display_name)

            # Pupnado
            rngval = random.random()
            dead_score = await sql.get_dead_score()
            puppy_score = await sql.get_puppy_score()
            if dead_is_here and dead_score > 30 and dead_score > puppy_score + 45 and rngval < self.CHANCE_PUPNADO:
                score_diff = (dead_score - puppy_score)
                by = int(score_diff * (random.random() * 0.2 + 0.9))
                await sql.update_puppy_score(by)
                return f"""
{ctx.author.mention} is walking down the road on an abnormally calm day. 
It is several minutes before he notices the low rumbling sound all around him... 
He looks behind him, and a look of terror strikes his face. 
He turns and starts sprinting away as fast as he can. But there is no way he 
can outrun it. The pupnado is soon upon him....
                        """

            if rngval < self.CHANCE_DOZEN:
                num = random.randint(8, 16)
                if ctx.author == deadinsky:
                    ref = 'Almost' if num < 12 else 'Over'
                    await sql.update_puppy_score(num)
                    return f'{ref} a dozen puppies suddenly fall from the sky onto {ctx.author.mention} ' \
                           f'and curbstomp him.'
                elif dead_is_here:
                    ref = 'maybe' if num < 12 else 'over'
                    await sql.update_puppy_score(num)
                    return f'{ctx.author.mention} watches as {ref} a dozen puppies spring from nowhere and ' \
                           f'ambush {deadinsky.display_name}, beating him to the curb.'
                else:
                    ref = 'nearly' if num < 12 else 'over'
                    return f'{ctx.author.mention} goes to kick a puppy on {deadinsky.display_name}\'s behalf, ' \
                           f'but instead gets ganged up on by {ref} a dozen puppies.'

            if rngval > 1 - self.CHANCE_DOZEN:
                num = random.randint(8, 13)
                if ctx.author == deadinsky:
                    await sql.update_dead_score(num)
                    return f'{ctx.author.mention} comes across a dog carrier with about a ' \
                           f'dozen puppies inside. He overturns the whole box with his foot!'
                elif dead_is_here:
                    ref = 'Maybe' if num < 12 else 'Over'
                    await sql.update_dead_score(num)
                    return f'{ctx.author.mention} watches as {deadinsky.display_name} punts a dog carrier. ' \
                           f'{ref} a dozen puppies run in terror from the overturned box.'
                else:
                    ref = 'nearly' if num < 12 else 'over'
                    return f'{ctx.author.mention} kicks a puppy on {deadinsky.display_name}\'s behalf. ' \
                           f'The pup flies into a nearby dog carrier with {ref} a dozen puppies inside and ' \
                           f'knocks it over.'

            if rngval < self.CHANCE_PUPWIN:
                if ctx.author == deadinsky:
                    await sql.update_puppy_score(1)
                    return f'A puppy kicks {ctx.author.mention}.'
                elif dead_is_here:
                    await sql.update_puppy_score(1)
                    return f'{ctx.author.mention} watches as a puppy kicks {deadinsky.display_name}\'s ass.'
                else:
                    return f'{ctx.author.mention} goes to kick a puppy on {deadinsky.display_name}\'s behalf, ' \
                           f'but instead the puppy dodges and kicks {ctx.author.mention}.'

            if ctx.author == deadinsky:
                await sql.update_dead_score(1)
                return f'{ctx.author.mention} kicks a puppy.'
            elif ctx.author.guild_permissions.manage_roles and random.random() < 0.05:
                role = discord.utils.find(lambda role: role.permissions.kick_members, reversed(ctx.guild.roles))
                if dead_is_here:
                    await sql.update_dead_score(1)
                    return f'{ctx.author.mention} watches as {deadinsky.display_name} accidentally ' \
                           f'makes a puppy an {role} while trying to kick it.'
                else:
                    return f'{ctx.author.mention} accidentally makes a puppy an {role} ' \
                           f'on {deadinsky.display_name}\'s behalf.'
            else:
                if dead_is_here:
                    await sql.update_dead_score(1)
                    return f'{ctx.author.mention} watches as {deadinsky.display_name} kicks a puppy.'
                else:
                    return f'{ctx.author.mention} kicks a puppy on {deadinsky.display_name}\'s behalf.'

    @commands.command(aliases=['kick'])
    async def pkick(self, ctx: commands.Context):
        """Kick a puppy"""
        await ctx.send(await self.do_kick(ctx))

    @staticmethod
    def pkick_replace(content, deadname: str) -> str:
        foo = 'PLACEHOLDER'
        while foo in content:
            foo = ''.join(random.choices(string.ascii_uppercase, k=11))
        content = content.replace('puppy', foo).replace('puppie', foo).replace('pup', foo)
        content = content.replace('Puppy', foo).replace('Puppie', foo).replace('Pup', foo)
        content = content.replace(deadname, 'puppy').replace(foo, deadname)
        if content.startswith('pupp'):
            content = content.capitalize()
        return content

    @commands.command()
    async def dkick(self, ctx: commands.Context):
        """Kick a deadinsky"""
        deadinsky = self.deadinsky(ctx)
        content = await self.do_kick(ctx)
        if not isinstance(deadinsky, discord.Member) or deadinsky.status != discord.Status.online:
            content = self.pkick_replace(content, deadinsky.display_name)
        await ctx.send(content)

    @commands.command(aliases=['pscore', 'score'])
    async def dscore(self, ctx: commands.Context):
        """Show the puppy score"""
        deadinsky = self.deadinsky(ctx)
        async with self.bot.sql as sql:
            dead_score = await sql.get_dead_score()
            puppy_score = await sql.get_puppy_score()

        if 66 < dead_score < 77:
            await ctx.send(f'{deadinsky.display_name}: 66+{dead_score - 66}, Puppies: {puppy_score}')
        else:
            await ctx.send(f'{deadinsky.display_name}: {dead_score}, Puppies: {puppy_score}')

    @commands.command()
    async def ckick(self, ctx: commands.Context):
        """Kick a cat"""
        catrevenge = [
            f"the cat wraps around {ctx.author.mention}'s leg and scratches it violently.",
            f"the cat dodges and jumps onto {ctx.author.mention}'s face.",
            f"misses, and the cat trips {ctx.author.mention} instead.",
            f"is instead crushed by a sudden army of cats HALO jumping in from above.",
            f"{ctx.author.mention} slips hard on the cat's squeeky toy and falls in the cat's litterbox.",
            f"the cat springs into the air and claws {ctx.author.mention} in the face before the kick connects.",
            f"the cat is a bastard and simply doesn't let it happen.",
        ]
        await ctx.send(f'{ctx.author.mention} goes to kick a cat, but {random.choice(catrevenge)}')

    async def dead_arrives(self, deadinsky: discord.Member):
        rngval = random.random()
        if rngval < self.CHANCE_URANIUM:
            async with self.bot.sql as sql:
                await sql.puppy_add_uranium()
            return f'As {deadinsky.display_name} walks into the room, he accidentally steps on some ' \
                   f'{self.NAME_URANIUM}. He pockets it.'
        elif rngval < 0.45:
            puppy_actions = [
                    f'a bucket falls on his head and two puppies fall down on it and smack it. '
                    f'They run off as {deadinsky.display_name} gets his bearings.',
                    f'a cup of warm coffee flies across the room from a dense group of puppies and '
                    f'beans {deadinsky.display_name} in the head.',
                    f'he steps on a rake with a bone attached to the end of it. It smacks him across the face.',
                    f'suddenly a whip creame pie smacks into his face. The puppies in the room scatter.',
                    f'a puppy swings from the ceiling, leaps off, and kicks him in the face, before running off.'
            ]
            async with self.bot.sql as sql:
                await sql.update_puppy_score(1)
            return f'{deadinsky.display_name} walks into the room and {random.choice(puppy_actions)}'
        else:
            return f'As {deadinsky.display_name} walks into the room, the puppies in the area tense up ' \
                   f'and turn to face him.'

    # Listen for when Deadinsky comes online
    @BaseCog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.id == PuppyWars.DEADINSKY:
            if after.status in self.ONLINE_STATES and before.status not in self.ONLINE_STATES:
                time_remaining = self.COOLDOWN[after.guild.id].update_rate_limit()
                if not time_remaining:
                    content = await self.dead_arrives(after)
                    channel = discord.utils.find(lambda ch: ch.permissions_for(after.guild.me).send_messages, after.guild.text_channels)
                    if channel is not None:
                        await channel.send(content)


def setup(bot):
    bot.add_cog(PuppyWars(bot))
