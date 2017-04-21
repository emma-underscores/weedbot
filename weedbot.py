import os
import os.path

import ComicGenerator

import discord
from discord.ext import commands


class ComicBot(commands.Bot):
    def __init__(self, command_prefix='?'):
        description = '''An bot for making shitty comics.'''
        commands.Bot.__init__(self, command_prefix='?', description=description)
        self.gen = ComicGenerator.ComicGenerator()
    

if __name__ == "__main__":

    token = os.environ['WEEDBOT_TOKEN']
    weedbot = ComicBot()

    @weedbot.event
    async def on_ready():
        print('Logged in as')
        print(weedbot.user.name)
        print(weedbot.user.id)
        print('------')

    @weedbot.command(pass_context=True)
    async def comic(ctx, numberofmessages : int):
        """Create an comic from the last x messages and post it.
        """
        maxmessages = 10
        if 0 > numberofmessages > maxmessages:
            await weedbot.say("Must be from 1 to " + maxmessages + " messages")
        else:
            channel = ctx.message.channel
    weedbot.run(token)
