#!/usr/bin/env python

import re
import sys
import logging
import logging.handlers

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.web.client import getPage

TICKET_RE = re.compile(r'#(\d+)')
COMMIT_RE = re.compile(r'r(\d+)')
BUILD_RE = re.compile(r'build ([\w\-]+)')

LOG_BLACKLIST = [
    'evn',
]
LOG_FILE = '/var/log/cassandra/irc-log'

BUILD_TOKEN = 'xxxxxxxxxxxx'
BUILD_URL = 'http://hudson.zones.apache.org/hudson/job'

logger = logging.getLogger()
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILE, 'midnight', 1)
formatter = logging.Formatter("%(asctime)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class CassBot(irc.IRCClient):
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)
    
    def signedOn(self):
        self.join(self.factory.channel)
        print "Signed on as %s." % (self.nickname,)
    
    def joined(self, channel):
        print "Joined %s." % (channel,)
    
    def ticketCallback(self, user, msg):
        match = TICKET_RE.search(msg)
        if not match:
            return
        ticket = int(match.group(1))
        url = 'http://issues.apache.org/jira/browse/CASSANDRA-%d' % (ticket,)
        self.msg(self.factory.channel, url)
    
    def logsCallback(self, user, msg):
        if self.nickname.lower() not in msg.lower():
            return
        if 'logs' not in msg.lower():
            return
        self.msg(self.factory.channel, 'http://www.eflorenzano.com/cassbot/')

    def commitCallback(self, user, msg):
        match = COMMIT_RE.search(msg)
        if not match:
            return
        commit = int(match.group(1))
        url = 'http://svn.apache.org/viewvc?view=rev&revision=%d' % (commit,)
        self.msg(self.factory.channel, url)

    def buildCallback(self, user, msg):
        if self.nickname.lower() not in msg.lower():
            return

        match = BUILD_RE.search(msg)
        if not match:
            return

        build = match.group(1)
        url = '%s/%s/polling?token=%s' % (BUILD_URL, build, BUILD_TOKEN)
        user = user.split('!', 1)[0]

        # Hudson returns a 404 even when this request succeeds :/
        def queued(result):
            self.msg(self.factory.channel, "%s: request sent!" % (user,))
        dfr = getPage(url).addCallbacks(callback=queued, errback=queued)
    
    def privmsg(self, user, channel, msg):
        if not user:
            return
        if not user.split('|')[0].rstrip('_') in LOG_BLACKLIST:
            logging.info('<' + user.split('!')[0] + '> ' + msg)
        self.ticketCallback(user, msg)
        self.logsCallback(user, msg)
        self.commitCallback(user, msg)
        self.buildCallback(user, msg)


class CassBotFactory(protocol.ReconnectingClientFactory):
    protocol = CassBot
    
    def __init__(self, channel='#cassandra', nickname='CassBot'):
        self.channel = channel
        self.nickname = nickname

 
if __name__ == "__main__":
    reactor.connectTCP('irc.freenode.net', 6667, CassBotFactory())
    reactor.run()
