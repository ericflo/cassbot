#!/usr/bin/env python

import re
import sys
import logging
import logging.handlers

from twisted.words.protocols import irc
from twisted.internet import reactor, defer, protocol
from twisted.web.client import getPage
from twisted.web.error import Error

TICKET_RE = re.compile(r'#(\d+)')
COMMIT_RE = re.compile(r'r(\d+)')

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
        for chan in self.factory.channels:
            self.join(chan)
        print "Signed on as %s." % (self.nickname,)
    
    def joined(self, channel):
        print "Joined %s." % (channel,)
    
    def checklinks(self, user, msg):
        match = TICKET_RE.search(msg)
        if match:
            ticket = int(match.group(1))
            url = 'http://issues.apache.org/jira/browse/CASSANDRA-%d' % (ticket,)
            self.msg(user, url)
        else:
            match = COMMIT_RE.search(msg)
            if match:
                commit = int(match.group(1))
                url = 'http://svn.apache.org/viewvc?view=rev&revision=%d' % (commit,)
                self.msg(user, url)
    
    def command_LOGS(self, user, channel, args):
        self.msg(channel, 'http://www.eflorenzano.com/cassbot/')

    @defer.inlineCallbacks
    def command_BUILD(self, user, channel, args):
        if not args[0]:
            self.msg(channel, "usage: build <buildname>")
            return
        url = '%s/%s/polling?token=%s' % (BUILD_URL, args[0], BUILD_TOKEN)
        msg = "request sent!"
        try:
            res = yield getPage(url)
        except Error, e:
            # Hudson returns a 404 even when this request succeeds :/
            if e.status == '404':
                pass
            else:
                msg = str(e)
        if user != channel:
            msg = user + ': ' + msg
        self.msg(channel, msg)
    
    def privmsg(self, user, channel, msg):
        user = user.split('!', 1)[0]
        if msg.startswith("%s" % self.nickname):
            msg = msg[len("%s" % self.nickname):]
            msg = msg.lstrip(';: ')
        elif channel == self.nickname:
            channel = user
        else:
            if user not in LOG_BLACKLIST:
                logging.info('[%s] <%s> %s' % (channel, user, msg))
            self.checklinks(channel, msg)
            return
        parts = msg.split(' ', 1)
        if len(parts) == 1:
            parts = parts + ['']
        cmd, args = parts
        meth = getattr(self, 'command_' + cmd.upper(), None)
        if meth:
            try:
                meth(user, channel, args)
            except Exception, e:
                print "Exception in %s: %s" % (cmd, e)
                self.msg(channel, "Ah crap, I got an exception :(")
        else:
            self.msg(channel, "Unknown command: %s" % cmd)

class CassBotFactory(protocol.ReconnectingClientFactory):
    protocol = CassBot
    
    def __init__(self, channels=['#cassandra', '#cassandra-dev'], nickname='CassBot'):
        self.channels = channels
        self.nickname = nickname

 
if __name__ == "__main__":
    reactor.connectTCP('irc.freenode.net', 6667, CassBotFactory())
    reactor.run()
