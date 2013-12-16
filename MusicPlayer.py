__author__ = 'daniel michels'

import json, sys


from threading import Timer
from gmusicapi import Mobileclient, Webclient
from mplayer import Player
from twisted.internet import reactor
from twisted.web import static, server

from autobahn.websocket import listenWS
from autobahn.wamp import WampServerFactory, WampServerProtocol, exportRpc

USERNAME = argv[1]
PASSWORD = argv[2]


class MusicPlayer(object):

    def __init__(self):
        self.currentTrack = 0
        self.playlist = []
        self.player = Player()
        self.webApi = Webclient()        # Client for WebInterface
        self.mobileApi = Mobileclient()  # Client for MobileInterface
        self.timer = None
        self.deviceid = 0

    def login(self, username, password):
        """ Login to Google Music.

        Keyword arguments:
        username -- the username
        password -- the password

        """
        print self.webApi.login(username, password)
        print self.mobileApi.login(username, password)

        # Use first found devices as ID
        devices = self.webApi.get_registered_devices();

        # Convert HEX to INT
        self.deviceid = int(devices[0]['id'], 16)

    def addTrackToPlaylist(self, track):
        """ Append a track to the end of playlist

        Keyword arguments:
        track -- a dictionary containing the track informations

        """
        self.playlist.append(track)

    def playTrack(self, trackPosition):
        """ Play a track

        Keyword arguments:
        trackPosition -- the position of the track in the playlist

        Returns:
        True or False

        """
        if len(self.playlist) - 1 < trackPosition:
            # trackPosition is to big. Return False.
            return False
        else:
            # Set trackPosition as currentTrack
            self.currentTrack = trackPosition

            # Load Track information from playlist
            track = self.playlist[trackPosition]

            # Request stream url from google music
            stream_url = self.mobileApi.get_stream_url(track["nid"], self.deviceid)

            # Load stream url to mplayer
            self.player.loadfile(stream_url)

            # Cancel previous timer
            if self.timer is not None:
                self.timer.cancel()

            # How many minutes does the track last
            trackDuration = long(track["durationMillis"]) / 1000

            # Set Timer to play next track when trackDuration is over
            self.timer = Timer(trackDuration, self.playNextTrack)
            self.timer.daemon = True
            self.timer.start()

            print "playing", track["artist"], " - ", track["title"], " : ", stream_url

            # Fire event that a new track is playing
            factory.forwarder.dispatch("musicplayer/playingtrack", json.dumps(track))

            return True

    def playNextTrack(self):
        """ Play the next track in the playlist. Or if the end of the playlist is reached start from the beginning.

        """
        self.currentTrack += 1

        if self.currentTrack >= len(self.playlist):
            self.currentTrack = 0

        return self.playTrack(self.currentTrack)

    def playPreviousTrack(self):
        self.currentTrack -= 1

        if self.currentTrack < 0:
            self.currentTrack = 0

        self.playTrack(self.currentTrack)

    def stop(self):
        if(self.timer is not None):
            self.timer.cancel()

        if(self.player is not None):
            self.player.stop()

    def play(self):
        self.playTrack(self.currentTrack)


class RpcServerProtocol(WampServerProtocol):

    @exportRpc
    def search(self, query):
        return json.dumps(musicplayer.mobileApi.search_all_access(query, 20)['song_hits'])

    @exportRpc
    def play(self, trackPosition):
        return musicplayer.playTrack(trackPosition)

    @exportRpc
    def getPlaylist(self):
        return json.dumps(musicplayer.playlist)

    @exportRpc
    def playNextTrack(self):
        return musicplayer.playNextTrack()

    @exportRpc
    def playPreviousTrack(self):
        return musicplayer.playPreviousTrack()

    @exportRpc
    def stop(self):
        return musicplayer.stop()

    @exportRpc
    def startPlaying(self):
        return musicplayer.play()

    @exportRpc
    def getStatus(self):
        status = dict()
        status['currentTrack'] = musicplayer.playlist[musicplayer.currentTrack]
        status['playing'] = musicplayer.player._args
        return json.dumps(status)

    @exportRpc
    def addToPlaylist(self, trackJson):
        # Convert Json to dictionary
        track = json.loads(trackJson)

        # Append track to playlist
        musicplayer.addTrackToPlaylist(track)

        # Notify all clients about the new track
        self.dispatch("musicplayer/newtrack", trackJson)

    def onSessionOpen(self):
        self.registerForPubSub("musicplayer/newtrack")
        self.registerForPubSub("musicplayer/playingtrack")
        self.registerForRpc(self, "musicplayer/music#")
        factory.forwarder = self


musicplayer = MusicPlayer()
musicplayer.login(USERNAME, PASSWORD)

if __name__ == '__main__':
    factory = WampServerFactory("ws://localhost:9000")
    factory.protocol = RpcServerProtocol
    listenWS(factory)

    root = static.File("web/")
    site = server.Site(root)
    reactor.listenTCP(8080, site)
    reactor.run()