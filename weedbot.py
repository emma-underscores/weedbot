import os
import os.path
import os.environ

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

if __name__ == "__main__":

    token = os.environ['WEEDBOT_TOKEN']

    weedbot.run(token)
