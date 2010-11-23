#!/usr/bin/env python

import re
import sys
from twisted.words.protocols import irc
from twisted.internet import reactor, defer, protocol
from twisted.web.client import getPage
from twisted.web.error import Error
from twisted.python import log, logfile

TICKET_RE = re.compile(r'(?:^|[]\s[(){}<>/:",-])#(\d+)\b')
COMMIT_RE = re.compile(r'\br(\d+)\b')

# This was the original. It was broken.
# COMMIT_RE = re.compile(r'r(\d+)')

LOG_BLACKLIST = [
    'evn',
]
LOG_FILE = '/var/log/cassandra/irc-log'

BUILD_TOKEN = 'xxxxxxxxxxxx'
BUILD_URL = 'http://hudson.zones.apache.org/hudson/job'

class CassBot(irc.IRCClient):
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)

    def irclog(self, *a, **kw):
        kw['mtype'] = 'irclog'
        return log.msg(*a, **kw)

    def signedOn(self):
        for chan in self.factory.channels:
            self.join(chan)
        self.irclog("Signed on as %s." % (self.nickname,))

    def joined(self, channel):
        self.irclog("Joined %s." % (channel,))

    def left(self, channel):
        self.irclog("Left %s." % (channel,))

    def noticed(self, user, chan, msg):
        self.irclog("NOTICE -!- [%s] <%s> %s" % (chan, user, msg))

    def modeChanged(self, user, chan, being_set, modes, args):
        self.irclog("MODE -!- %s %s modes %r in %r for %r" % (
            user,
            'set' if being_set else 'unset',
            modes,
            chan,
            args
        ))

    def kickedFrom(self, chan, kicker, msg):
        self.irclog('KICKED -!- from %s by %s [%s]' % (chan, kicker, msg))

    def nickChanged(self, nick):
        self.irclog('NICKCHANGE -!- my nick changed to %s' % (nick,))

    def userJoined(self, user, chan):
        self.irclog('%s joined %s' % (user, chan))

    def userLeft(self, user, chan):
        self.irclog('%s left %s' % (user, chan))

    def userQuit(self, user, msg):
        self.irclog('%s quit [%s]' % (user, msg))

    def userKicked(self, kickee, chan, kicker, msg):
        self.irclog('%s was kicked from %s by %s [%s]' % (kickee, chan, kicker, msg))

    def action(self, user, chan, data):
        self.irclog('[%s] * %s %s' % (chan, user, data))

    def topicUpdated(self, user, chan, newtopic):
        self.irclog('[%s] -!- topic changed by %s to %r' % (chan, user, newtopic))

    def userRenamed(self, oldname, newname):
        self.irclog('RENAME %s is now known as %s' % (oldname, newname))

    def receivedMOTD(self, motd):
        self.irclog('MOTD %s' % (motd,))

    def checktickets(self, user, msg):
        for match in TICKET_RE.finditer(msg):
            ticket = int(match.group(1))
            url = 'http://issues.apache.org/jira/browse/CASSANDRA-%d' % (ticket,)
            self.msg(user, url)

    def checkrevs(self, user, msg):
        for match in COMMIT_RE.finditer(msg):
            commit = int(match.group(1))
            url = 'http://svn.apache.org/viewvc?view=rev&revision=%d' % (commit,)
            self.msg(user, url)

    def checklinks(self, user, msg):
        self.checktickets(user, msg)
        self.checkrevs(user, msg)

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

    def msg(self, dest, msg, length=None):
        self.irclog('[%s] <%s> %s' % (dest, self.nickname, msg))
        irc.IRCClient.msg(self, dest, msg, length=length)

    def privmsg(self, user, channel, msg):
        user = user.split('!', 1)[0]
        if user not in LOG_BLACKLIST:
            self.irclog('[%s] <%s> %s' % (channel, user, msg))
        if msg.lower().startswith(self.nickname.lower()):
            msg = msg[len(self.nickname):]
            msg = msg.lstrip(';: ')
            self.process_commands(user, channel, msg)
        elif channel == self.nickname:
            channel = user
            self.process_commands(user, channel, msg)
        self.checklinks(channel, msg)

    @defer.inlineCallbacks
    def process_commands(self, user, channel, msg):
        parts = msg.split(None, 1)
        cmd = parts[0]
        args = parts[1:]
        meth = getattr(self, 'command_' + cmd.upper(), None)
        if meth:
            try:
                yield meth(user, channel, args)
            except Exception:
                log.err(None, "Exception in %s" % (cmd,))
                self.msg(channel, "Ah crap, I got an exception :(")
        else:
            self.msg(channel, "Unknown command: %s" % cmd)

class CassBotFactory(protocol.ReconnectingClientFactory):
    protocol = CassBot
    
    def __init__(self, channels=['#cassandra', '#cassandra-dev'], nickname='CassBot'):
        self.channels = channels
        self.nickname = nickname

 
if __name__ == "__main__":
    logf = logfile.DailyLogFile.fromFullPath(LOG_FILE)
    observer = log.FileLogObserver(logf)
    log.startLoggingWithObserver(observer)

    reactor.connectTCP('irc.freenode.net', 6667, CassBotFactory())
    reactor.run()
