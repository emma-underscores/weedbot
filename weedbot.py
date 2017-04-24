import os
import os.path
import io
import logging
import asyncio

import ComicGenerator

import discord
from discord.ext import commands

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class Weedbot:
    def __init__(self, bot, maxmessages=10):
        description = '''An bot for making shitty comics.'''
        self.bot = bot
        self.gen = ComicGenerator.ComicGenerator()
        self.maxmessages = maxmessages

        
    @commands.command(pass_context=True, no_pm=True)
    async def comic(self, ctx, numberofmessages):
        """Create an comic from the last x messages and post it.
        """
        logger.info('Running comic command')
        channel = ctx.message.channel
        try:
            numberofmessages = int(numberofmessages)
        except ValueError:
            await self.bot.say("Must be a number from 1 to {}.".format(self.maxmessages))
        else:
            if 0 < numberofmessages <= self.maxmessages:
                messages=[]
                async for message in self.bot.logs_from(channel, numberofmessages, before=ctx.message):
                    messages.append(message)
                img = self.gen.make_comic(messages)
                img_io = io.BytesIO()
                img.save(img_io, 'JPEG', quality=90)
                img_io.seek(0)
                await self.bot.send_file(channel, img_io, filename='weedbot.jpg')
                img_io.close()
            else:
                await self.bot.say("Must be from 1 to {}.".format(maxmessages))


if __name__ == "__main__":

    token = os.environ['WEEDBOT_TOKEN']
    description = '''An bot for making shitty comics.'''
    
    bot = commands.Bot(command_prefix='?', description=description)
    weedbot = Weedbot(bot)
    bot.add_cog(Weedbot(bot))

    @bot.event
    async def on_ready(self):
        logger.info('Logged in as {0} {1}'.format(self.user.name, self.user.id))
    
    weedbot.bot.run(token)
