#!/usr/bin/evn python

from array import array
from fcntl import ioctl
from ircbot import SingleServerIRCBot
from irclib import irc_lower,nm_to_n
from threading import *

import SocketServer
import os
import re
import socket
import string
import sys
import time
import types
import urllib
import xml.etree.cElementTree as etree

class NoisebartBot(SingleServerIRCBot):
    bart_key = "MW9S-E7SL-26DU-VV8V"

    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.stations = []
        self.read_stations(self.stations)

    def read_stations(self, stations):
        station_feed = \
            "http://api.bart.gov/api/stn.aspx?cmd=stns&key=%s" \
                % NoisebartBot.bart_key

        f = urllib.urlopen(station_feed)
        station_list = etree.iterparse(f)
        for action, elem in station_list:
            if elem.tag == "station":
                name = elem.find("name").text
                abbr = elem.find("abbr").text
                self.stations.append((abbr, name))

    def reply(self, e, text):
        self.say_private(nm_to_n(e.source()), text)

    def say_public(self, text):
        "Print TEXT into public channel, for all to see."
        for chname, chobj in self.channels.items():
            self.connection.privmsg(self.channel, text)

    def say_private(self, nick, text):
        "Print TEXT to nick."
        self.connection.privmsg(nick, text)

    def parse_station(self, station_input):
        results = []
        station_input = station_input.replace("_", " ")
        for station in self.stations:
            fullname = station[1]
            if fullname.lower().find(station_input.lower()) != -1:
                results.append(station)
        return results

    def get_times(self, orig, dest):
        times = []
        schedule_feed = \
            "http://api.bart.gov/api/" \
          + "sched.aspx?cmd=depart&orig=%s&dest=%s&key=%s" \
              % (orig, dest, NoisebartBot.bart_key)

        f = urllib.urlopen(schedule_feed)
        schedule = etree.iterparse(f)
        for action, elem in schedule:
            if elem.tag == "trip":
                time = re.sub(r'\s(?:AM|PM)', '', elem.get("origTimeMin"))
                fare = elem.get("fare")
                times.append(time)
        return (times, fare)

    def cmd_times(self, args, e):
        if args[0] == "help":
            self.cmd_help([], e)
            return

        try:
            rep = ""

            orig = self.parse_station(args[0])
            if len(orig) < 1:
                rep += "Unrecognized origin."
            elif len(orig) > 1:
                rep += "Origin is not specific enough."

            dest = self.parse_station(args[1])
            if len(dest) < 1:
                rep += "Unrecognized destination."
            elif len(dest) > 1:
                rep += "Destination is not specific enough."

            if len(orig) == 1 and len(dest) == 1:
                orig = orig.pop()
                orig_abbr = orig[0]
                orig_full = orig[1]

                dest = dest.pop()
                dest_abbr = dest[0]
                dest_full = dest[1]

                times, fare = self.get_times(orig_abbr, dest_abbr)
                rep += ("%s -> %s %s (COST: %s)" \
                     % (orig_full, dest_full, self.format_times(times), fare))
        except Exception, ex:
            rep = str(ex)
        finally:
            self.reply(e, rep)

    def format_times(self, times):
        res = "("
        for time in times:
            res += time + ", "
        res = res.strip()[:-1]
        res += ")"
        return res


    def on_pubmsg(self, c, e):
        if nm_to_n(e.source()).find("noise") != -1:
            return
        a = string.split(e.arguments()[0], ":", 1)
        if len(a) > 1 and irc_lower(a[0]) == irc_lower(c.get_nickname()):
            self.do_command(e, string.strip(a[1]))
        if irc_lower(e.arguments()[0]).find(".bart") == 0:
            self.cmd_times(e.arguments()[0].strip().split(" ")[1:], e)

    def on_privmsg(self, c, e):
        if nm_to_n(e.source()) == "NickServ":
            password = file('identpass').readline().strip()
            self.reply(e, "identify %s" % password)
        self.do_command(e, e.arguments()[0].strip())

    def cmd_help(self, args, e):
        self.reply(e, \
                "Usage: .bart <orig> <dest>" \
              + "  or  noisebart: times <orig> <dest>" \
              + "  or  /msg noisebart times <orig> <dest>")
        self.reply(e, "Station list:")
        msg = ""
        # ???: TypeError: enumerate() takes no arguments (1 given)
        i=0
        for station in sorted(self.stations, key=lambda x: x[0]):
            msg += ("%s; " % station[1])
            if i % 28 == 0 and i != 0:
                self.reply(e, msg)
                msg = ""
            i+=1
        self.reply(e, msg)

    def do_command(self, e, cmd):
        cmds = cmd.strip().split(" ")
        try:
            cmd_handler = getattr(self, "cmd_" + cmds[0])
        except AttributeError:
            cmd_handler = None
        if cmd_handler:
            cmd_handler(cmds[1:], e)
            return

        self.reply(e, "I don't understand '%s'."%(cmd))

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

def main():
    bot = NoisebartBot("#noisetest2", "noisebart", "irc.freenode.net", 6667)
    bot.start()

if __name__ == "__main__":
    main()

