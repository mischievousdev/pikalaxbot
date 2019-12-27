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

import asyncio
import discord
import binascii
from discord.ext import commands
from . import BaseCog
import time
import traceback
import typing
import base64

from .utils.errors import *


class Poll(BaseCog):
    TIMEOUT = 60

    def __init__(self, bot):
        super().__init__(bot)
        self.polls = {}

    async def do_poll(self, ctx: commands.Context, emojis: typing.List[str], msg: discord.Message):
        # This setup is to ensure that each user gets max one vote
        votes_d = {}

        def check1(rxn, athr):
            return rxn.message.id == msg.id and rxn.emoji in emojis and athr.id not in votes_d

        def check2(rxn, athr):
            return rxn.message.id == msg.id and rxn.emoji == votes_d.get(athr.id)

        try:
            while True:
                tasks = [
                    self.bot.wait_for('reaction_add', check=check1),
                    self.bot.wait_for('reaction_remove', check=check2)
                ]
                done, left = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                [task.cancel() for task in left]
                reaction, author = done.pop().result()
                if author in (self.bot.user, ctx.author):
                    continue
                vote = votes_d.get(author.id)
                if vote is None:  # This was a reaction_add event
                    votes_d[author.id] = reaction.emoji
                elif vote == reaction.emoji:  # This was a reaction_remove event
                    del votes_d[author.id]
                else:
                    raise ReactionIntegrityError('Our checks passed when neither should have!')
        except asyncio.CancelledError:
            votes_l = list(votes_d.values())
            votes = [votes_l.count(emoji) for emoji in emojis]
            return votes

    @commands.group(name='poll', invoke_without_command=True)
    async def poll_cmd(self, ctx: commands.Context, timeout: typing.Optional[int], prompt, *opts):
        """Create a poll with up to 10 options.  Poll will last for 60 seconds, with sudden death
        tiebreakers as needed.  Use quotes to enclose multi-word prompt and options.
        Optionally, pass an int before the prompt to indicate the number of seconds the poll lasts."""
        timeout = timeout or Poll.TIMEOUT
        # Do it this way because `set` does weird things with ordering
        options = []
        for opt in opts:
            if opt not in options:
                options.append(opt)
        nopts = len(options)
        if nopts > 10:
            raise TooManyOptions('Too many options!')
        if nopts < 2:
            raise NotEnoughOptions('Not enough unique options!')
        nopt = len(options)
        emojis = [f'{i + 1}\u20e3' if i < 9 else '\U0001f51f' for i in range(nopt)]
        start = time.time()
        my_hash = hash((start, ctx.channel, ctx.author)) & 0xFFFFFFFF
        enc = base64.b32encode(my_hash.to_bytes(4, 'little')).decode().rstrip('=')
        content = f'Vote using emoji reactions. ' \
                  f'You have {timeout:d} seconds from when the last option appears. ' \
                  f'Max one vote per user. ' \
                  f'To change your vote, clear your original selection first. ' \
                  f'The poll author may not cast a vote. ' \
                  f'The poll author may cancel the poll using `{ctx.prefix}{self.cancel.qualified_name} {enc}`'
        description = '\n'.join(f'{emoji}: {option}' for emoji, option in zip(emojis, options))
        embed = discord.Embed(title=prompt, description=description)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        msg = await ctx.send(content, embed=embed)
        for emoji in emojis:
            await msg.add_reaction(emoji)
        task = asyncio.create_task(self.do_poll(ctx, emojis, msg))
        task._start_time = start
        task._sent_message = msg
        self.polls[my_hash] = task
        try:
            await asyncio.wait_for(task, timeout)
        except asyncio.TimeoutError:
            votes = task.result()
            description = '\n'.join(f'{emoji}: {option} ({vote})' for emoji, option, vote in zip(emojis, options, votes))
            embed = msg.embeds[0]
            embed.description = description
            argmax = max(range(nopts), key=lambda i: votes[i])
            await msg.edit(content=f'Poll closed, the winner is "{options[argmax]}"', embed=embed)
        finally:
            task = self.polls.pop(my_hash, None)
            if task is not None:
                task.cancel()

    @poll_cmd.command()
    async def cancel(self, ctx: commands.Context, code):
        """Cancel a running poll using a code. You must be the one who started the poll
        in the first place."""
        if len(code) & 7:
            code += '=' * (8 - (len(code) & 7))
        my_hash = int.from_bytes(base64.b32decode(code.encode()), 'little')
        task = self.polls.get(my_hash)
        if task is None:
            raise NoPollFound('The supplied code does not correspond to a running poll')
        test_hash = hash((task._start_time, ctx.channel, ctx.author)) & 0xFFFFFFFF
        if test_hash != my_hash:
            raise NotPollOwner('You may not cancel this poll')
        task.cancel()
        await task._sent_message.edit(content='The poll was cancelled.')

    async def cog_command_error(self, ctx, exc):
        handled_excs = \
            TooManyOptions, \
            NotEnoughOptions, \
            ReactionIntegrityError, \
            commands.CheckFailure, \
            asyncio.CancelledError, \
            asyncio.TimeoutError, \
            NotPollOwner, \
            NoPollFound, \
            binascii.Error
        exc = getattr(exc, 'original', exc)
        await ctx.send(f'{exc.__class__.__name__}: {exc} {self.bot.command_error_emoji}', delete_after=10)
        if not isinstance(exc, handled_excs):
            tb = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__, 4))
            embed = discord.Embed(color=discord.Color.red(), title='Poll exception', description=f'```\n{tb}\n```')
            embed.add_field(name='Author', value=ctx.author.mention)
            embed.add_field(name='Channel', value=ctx.channel.mention)
            embed.add_field(name='Message', value=ctx.message.jump_url)
            await self.bot.owner.send(embed=embed)


def setup(bot):
    bot.add_cog(Poll(bot))
