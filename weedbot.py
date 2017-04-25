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
        self.autotime = 120 # 2 minutes
        self.autochars = 3 # 3 people

    async def send_image(self, channel, img):
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=90)
        img_io.seek(0)
        await self.bot.send_file(channel, img_io, filename='weedbot.jpg')
        logger.info("sent image")
        img_io.close()

    def auto_filter_messages(self, messages):
        logger.info("filtering messages")
        automessages = messages[:1]
        chars = {messages[0].author.id}
        for message, nextmessage in zip(messages, messages[1:]):
            logger.info("{0} - {1} = {2}".format(message.timestamp, nextmessage.timestamp, (message.timestamp - nextmessage.timestamp).total_seconds()))
            chars.add(nextmessage.author.id)
            if len(chars) > self.autochars:
                logger.info("Too many characters")
                break
            if (message.timestamp - nextmessage.timestamp).total_seconds() < self.autotime:
                automessages.append(nextmessage)
            else:
                logger.info("Timestamp diff of {}".format((message.timestamp - nextmessage.timestamp).total_seconds()))
                break
        return automessages

   
    @commands.command(pass_context=True, no_pm=True, aliases=['Comic','weed','weedbot'])
    async def comic(self, ctx, numberofmessages=None):
        """Create an comic from the last few messages and post it.
Uses recent messages posted within 2 minutes of each other, up to 3 people and 10 messages.
Can also use input of 1 to 10 to use last x messages instead.
        """
        channel = ctx.message.channel
        if numberofmessages is None:
            logger.info('Running comic command on auto')
            unfilteredmessages=[]
            async for message in self.bot.logs_from(channel, self.maxmessages, before=ctx.message):
                unfilteredmessages.append(message)
            messages = self.auto_filter_messages(unfilteredmessages)
            img = self.gen.make_comic(messages)
            await self.send_image(channel, img)
            await self.bot.delete_message(ctx.message)
            return
        try:
            numberofmessages = int(numberofmessages)
        except ValueError:
            await self.bot.say("Must be a number from 1 to {}.".format(self.maxmessages))
        else:
            if 0 < numberofmessages <= self.maxmessages:
                logger.info('Running comic command with: {}'.format(numberofmessages))
                messages=[]
                async for message in self.bot.logs_from(channel, numberofmessages, before=ctx.message):
                    messages.append(message)
                img = self.gen.make_comic(messages)
                await self.send_image(channel, img)
                await self.bot.delete_message(ctx.message)
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
