    
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

from discord.ext import commands
from . import BaseCog

MORSE_CODE_DICT = { 'A':'.-', 'B':'-...', 'C':'-.-.',
                    'D':'-..', 'E':'.', 'F':'..-.',
                    'G':'--.', 'H':'....', 'I':'..',
                    'J':'.---', 'K':'-.-', 'L':'.-..',
                    'M':'--', 'N':'-.', 'O':'---',
                    'P':'.--.', 'Q':'--.-', 'R':'.-.',
                    'S':'...', 'T':'-', 'U':'..-',
                    'V':'...-', 'W':'.--', 'X':'-..-',
                    'Y':'-.--', 'Z':'--..', '1':'.----',
                    '2':'..---', '3':'...--', '4':'....-',
                    '5':'.....', '6':'-....', '7':'--...',
                    '8':'---..', '9':'----.', '0':'-----',
                    ',':'--..--', '.':'.-.-.-', '?':'..--..',
                    '!':'-.-.--', '/':'-..-.', '-':'-....-',
                    '(':'-.--.', ')':'-.--.-', "'":'.----.',
                    '&':'.-...', ':':'---...', ';':'-.-.-.', 
                    '=':'-...-', '+':'.-.-.', '_':'..--.-',
                    '"':'.-..-.', '$':'...-..-', '@':'.--.-.'}


def reverse_horse_lookup(code, default=None):
    for k, v in MORSE_CODE_DICT.items():
        if v == code:
            return k
    return default


def horse_encode(input_str):
    return ' / '.join(' '.join(MORSE_CODE_DICT.get(c, '#').replace('-', 'H').replace('.', 'h') for c in w) for w in input_str.upper().strip().split())


def horse_decode(input_str):
    return ' '.join(''.join(reverse_horse_lookup(c.replace('h', '.').replace('H', '-'), '#') for c in w.strip().split()) for w in input_str.strip().split('/'))


class HorseCode(BaseCog):
    @commands.group()
    async def horse(self, ctx: commands.Context):
        """Horse Code commands"""
    
    @horse.command()
    async def encode(self, ctx: commands.Context, *, input_str):
        """Encode a string to Horse Code"""
        await ctx.send(horse_encode(input_str))
    
    @horse.command()
    async def decode(self, ctx: commands.Context, *, input_str):
        """Decode a Horse Code string to English"""
        await ctx.send(horse_decode(input_str))


def setup(bot):
    bot.add_cog(HorseCode(bot))
