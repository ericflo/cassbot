#!/usr/bin/env python

import re
import sys
import logging
import logging.handlers

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

TICKET_RE = re.compile(r'#(\d+)')
COMMIT_RE = re.compile(r'r(\d+)')

LOG_BLACKLIST = [
    'evn',
]
LOG_FILE = '/var/log/cassandra/irc-log'

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
    
    def privmsg(self, user, channel, msg):
        if not user:
            return
        if not user.split('|')[0].rstrip('_') in LOG_BLACKLIST:
            logging.info('<' + user.split('!')[0] + '> ' + msg)
        self.ticketCallback(user, msg)
        self.logsCallback(user, msg)
        self.commitCallback(user, msg)

class CassBotFactory(protocol.ClientFactory):
    protocol = CassBot
    
    def __init__(self, channel='#cassandra', nickname='CassBot'):
        self.channel = channel
        self.nickname = nickname
    
    def clientConnectionLost(self, connector, reason):
        print >> sys.stderr, "Lost connection (%s), reconnecting." % (reason,)
        connector.connect()
    
    def clientConnectionFailed(self, connector, reason):
        print >> sys.stderr, "Could not connect: %s" % (reason,)
 
if __name__ == "__main__":
    reactor.connectTCP('irc.freenode.net', 6667, CassBotFactory())
    reactor.run()
