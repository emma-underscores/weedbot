import os
import os.path

import ComicGenerator

import discord
from discord.ext import commands


description = '''An bot for making shitty comics.'''

weedbot = commands.Bot(command_prefix='?', description=description)
weedbot.gen = ComicGenerator.ComicGenerator()
    
@weedbot.event
async def on_ready():
    print('Logged in as')
    print(weedbot.user.name)
    print(weedbot.user.id)
    print('------')

@weedbot.command(pass_context=True)
async def comic(ctx):
    """Create an comic from the last x messages and post it.
    """
    numberofmessages = int(ctx.args[0])
    maxmessages = 10
    if numberofmessages > maxmessages:
        weedbot.say("Must be from 1 to " + maxmessages + " messages")
    else:
        channel = ctx.message.channel
        lastxmessages = self.logs_from(channel, numberofmessages)
        img = self.gen.make_comic(lastxmessages)
        weedbot.send_file(channel, img)


if __name__ == "__main__":

    token = os.environ['WEEDBOT_TOKEN']

    weedbot.run(token)
