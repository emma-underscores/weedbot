import os
import os.path
import io
import logging

import ComicGenerator

import discord
from discord.ext import commands

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

maxmessages = 10


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
    async def comic(ctx, numberofmessages):
        """Create an comic from the last x messages and post it.
        """
        channel = ctx.message.channel
        try:
            numberofmessages = int(numberofmessages)
        except ValueError:
            await weedbot.say("Must be a number from 1 to {}.".format(maxmessages))
        else:
            if 0 < numberofmessages <= maxmessages:
                messages=[]
                async for message in weedbot.logs_from(channel, numberofmessages, before=ctx.message):
                    messages.append(message)
                img = weedbot.gen.make_comic(messages)
                img_io = io.BytesIO()
                img.save(img_io, 'JPEG', quality=90)
                img_io.seek(0)
                await weedbot.send_file(channel, img_io, filename='weedbot.jpg')
                img_io.close()
            else:
                await weedbot.say("Must be from 1 to {}.".format(maxmessages))


    weedbot.run(token)
