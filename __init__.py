# -*- coding: utf-8 -*-
# vim: set ts=4 et

# https://discord.com/oauth2/authorize?client_id=316297609474080768&permissions=36507356160&scope=bot applications.commands

import asyncio
import os
import sqlite3
from threading import Thread

from pybot.plugin import *

import discord
import discord.utils
from discord.channel import TextChannel


class DiscordClient(discord.Client):
    def __init__(self, plugin):
        discord.Client.__init__(self)
        self.plugin = plugin

    async def on_message(self, message):
        if message.author == self.user:
            return

        c = self.plugin.db.cursor()
        c.execute('SELECT IrcChannel FROM Mapping ' \
                  'WHERE DiscordId=?', (message.channel.id,))

        row = c.fetchone()
        if not row:
            return

        text = '<%s> %s' % (message.author.display_name, discord.utils.remove_markdown(message.clean_content))
        self.plugin.bot.privmsg(row[0], text)


class Plugin(BasePlugin):
    default_level = 1000

    def on_load(self):
        token = self.config['bot_token']

        self.client = DiscordClient(self)
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.client.start(token))

        self.db = sqlite3.connect(os.path.join(self.bot.core.data_path, 'discord.db'), check_same_thread=False)
        c = self.db.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS Mapping (
              IrcChannel VARCHAR(100) NOT NULL,
              DiscordId  INTEGER      NOT NULL,
              UNIQUE (IrcChannel, DiscordId)
            );''')
        self.db.commit()

        self.thread = Thread(target=self.loop.run_forever).start()


    def on_unload(self):
        # TODO: fix this to close event loop
        return True


    @hook
    def discord_link_trigger(self, msg, args, argstr):
        if not msg.channel:
            msg.reply('This trigger can only be used from a channel.')
            return

        if len(args) > 2:
            msg.reply('This trigger takes at most one argument.')
            return

        if len(args) == 1:
            c = self.db.cursor()
            c.execute('SELECT DiscordId from Mapping ' \
                      'WHERE IrcChannel = ?', (msg.channel,))
            row = c.fetchone()
            ch = None
            if row:
                ch = discord.utils.get(self.client.get_all_channels(), id=row[0])
            if ch:
                msg.reply('Linked to %s' % (ch.name,))
            else:
                msg.reply('Not linked')
            return

        name = args[1]
        if name.startswith('-'):
            name = name[1:]

            ch = discord.utils.find(lambda ch: isinstance(ch, TextChannel) and ch.name == name, self.client.get_all_channels())
            if not ch:
                msg.reply('Unknown discord channel.')
                return

            c = self.db.cursor()
            c.execute('DELETE FROM Mapping ' \
                    'WHERE DiscordId = ? LIMIT 1', (ch.id,))
            self.db.commit()
            msg.reply('Unlinked from %s' % (ch.name,))
            return

        ch = discord.utils.find(lambda ch: isinstance(ch, TextChannel) and ch.name == name, self.client.get_all_channels())
        if not ch:
            msg.reply('Unknown discord channel.')
            return

        c = self.db.cursor()
        c.execute('INSERT OR REPLACE INTO Mapping ' \
            'VALUES (?, ?)', (msg.channel, ch.id))
        self.db.commit()
        msg.reply('Linked to %s' % (ch.name,))


    @hook
    def privmsg_command(self, msg):
        if msg.trigger:
            return

        c = self.db.cursor()
        c.execute('SELECT DiscordId FROM Mapping ' \
                  'WHERE IrcChannel=?', (msg.channel.lower(),))
        row = c.fetchone()
        if not row:
            return

        text = '<%s> %s' % (msg.source, msg.param[-1])
        ch = discord.utils.get(self.client.get_all_channels(), id=row[0])
        if ch:
            asyncio.run_coroutine_threadsafe(ch.send(text), self.loop).result()
