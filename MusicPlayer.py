from Playlist import Playlist, PlayType

__author__ = 'daniel michels'

import json
import sys


from threading import Timer
from gmusicapi import Mobileclient, Webclient
from mplayer import Player
from twisted.internet import reactor
from twisted.web import static, server

from autobahn.websocket import listenWS
from autobahn.wamp import WampServerFactory, WampServerProtocol, exportRpc


PLAYLIST_EVENT_TRACK_ADDED = 'musicplayer/playlist/events/track_added_to_playlist'
PLAYLIST_EVENT_TRACK_REMOVED = 'musicplayer/playlist/events/track_removed_from_playlist'

PLAYLIST_EVENT_PLAYTYPE_CHANGED = 'musicplayer/playlist/events/playtype_changed'

TRACK_EVENT_PLAYBACK = 'musicplayer/events/playback'


class MusicPlayer(object):

    def __init__(self):
        self.playlist = Playlist()
        self.player = Player()
        self.webclient = Webclient()        # Client for WebInterface
        self.mobileclient = Mobileclient()  # Client for MobileInterface
        self.timer = None
        self.deviceid = 0

    def login(self, username, password):
        """ Login to Google Music.

        Keyword arguments:
        username -- the username
        password -- the password

        Returns:
        True if successful else False

        """

        # If either the web client or the mobile client failed to login return False
        if not self.webclient.login(username, password) or not self.mobileclient.login(username, password):
            return False

        # Use first found devices as ID
        devices = self.webclient.get_registered_devices();

        # Convert HEX to INT
        self.deviceid = int(devices[0]['id'], 16)

        return True

    def add_track_to_playlist(self, track):
        """ Append a track to the end of playlist

        Keyword arguments:
        track -- a dictionary containing the track informations

        Returns:
        True or False

        """
        result = self.playlist.add_track(track)

        if result:
            # Notify all clients about the new track
            factory.forwarder.dispatch(PLAYLIST_EVENT_TRACK_ADDED, json.dumps(track))

        return result

    def remove_track_from_playlist(self, track_id):
        """ Removes a track from the playlist

        Keyword arguments:
        track_id -- The id of the track to remove

        Returns:
        True or False

        """

        result = self.playlist.remove_track(track_id)

        # If track has been removed, notify all clients about it
        if result:
            factory.forwarder.dispatch(PLAYLIST_EVENT_TRACK_REMOVED, track_id)

        return result

    def play_track(self, track_id):
        """ Play a track

        Keyword arguments:
        track_id -- Id of the track to play

        Returns:
        True or False

        """

        # Get track from playlist
        track = self.playlist.get_track(track_id)
        if track is not None:
            # Request stream url from google music
            stream_url = self.mobileclient.get_stream_url(track["nid"], self.deviceid)

            # Load stream url to mplayer
            self.player.loadfile(stream_url)

            # For some reason OSX needs to unpause mplayer
            if sys.platform == "darwin":
                self.player.pause()

            # Set track
            self.playlist.set_current_track(track_id)

            # Cancel previous timer
            if self.timer is not None:
                self.timer.cancel()

            # How many minutes does the track last
            track_duration = long(track["durationMillis"]) / 1000

            # Set Timer to play next track when trackDuration is over
            self.timer = Timer(track_duration, self.play_next_track)
            self.timer.daemon = True
            self.timer.start()

            print "playing", track["artist"], " - ", track["title"], " : ", stream_url

            # Fire event that a new track is playing
            factory.forwarder.dispatch(TRACK_EVENT_PLAYBACK, json.dumps(track))

            return True
        else:
            return False

    def play_next_track(self):
        """ Play the next track in the playlist.

        Returns:
        True or False

        """

        # Obtain the id of the next track to play
        next_track_id = self.playlist.get_next_track_id()

        # Play track with that id
        return self.play_track(next_track_id)

    def play_previous_track(self):
        """ Play the previous track in the playlist.

        Returns:
        True or False

        """

        # Obtain the id of the previous track to play
        previous_track_id = self.playlist.get_previous_track_id()

        # Play track with that id
        return self.play_track(previous_track_id)

    def stop(self):
        """ Stop playback.

        """

        if self.timer is not None:
            self.timer.cancel()

        if self.player is not None:
            self.player.stop()

    def play(self):
        """ Start playing current track

        Returns:
        True if track has been started. Else False

        """
        current_track_id = self.playlist.get_current_track_id()
        return self.play_track(current_track_id)


class RpcServerProtocol(WampServerProtocol):

    @exportRpc
    def search(self, query):
        result = musicplayer.mobileclient.search_all_access(query, 20)

        return json.dumps(result['song_hits'])

    @exportRpc
    def play(self, track_id):
        result = dict()
        result['status'] = musicplayer.play_track(track_id)

        return json.dumps(result)

    @exportRpc
    def get_playlist(self):
        return json.dumps(musicplayer.playlist.get_tracks())

    @exportRpc
    def play_next_track(self):
        result = dict()
        result['status'] = musicplayer.play_next_track()
        return json.dumps(result)

    @exportRpc
    def play_previous_track(self):
        result = dict()
        result['status'] = musicplayer.play_previous_track()
        return json.dumps(result)

    @exportRpc
    def stop(self):
        result = dict()
        result['status'] = True

        # Actually stop player
        musicplayer.stop()

        return json.dumps(result)

    @exportRpc
    def startPlaying(self):
        result = dict()
        result['status'] = musicplayer.play()
        return json.dumps(result)

    @exportRpc
    def get_status(self):
        status = dict()

        try:
            current_track_id = musicplayer.playlist.get_current_track_id()

            current_track = musicplayer.playlist.get_track(current_track_id)

            status['currentTrack'] = current_track
        except:
            pass

        status['playtype'] = musicplayer.playlist.get_playtype()

        return json.dumps(status)

    @exportRpc
    def add_to_playlist(self, trackJson):
        result = dict()

        # Convert Json to dictionary
        track = json.loads(trackJson)

        # Append track to playlist
        result['status'] = musicplayer.add_track_to_playlist(track)

        return json.dumps(result)

    @exportRpc
    def remove_from_playlist(self, track_id):
        return musicplayer.remove_track_from_playlist(track_id)

    @exportRpc
    def set_playtype(self, playtype):
        musicplayer.playlist.set_playtype(playtype)
        self.dispatch(PLAYLIST_EVENT_PLAYTYPE_CHANGED, playtype)

    def onSessionOpen(self):
        self.registerForPubSub(PLAYLIST_EVENT_TRACK_ADDED)
        self.registerForPubSub(PLAYLIST_EVENT_TRACK_REMOVED)
        self.registerForPubSub(PLAYLIST_EVENT_PLAYTYPE_CHANGED)
        self.registerForPubSub(TRACK_EVENT_PLAYBACK)

        self.registerForRpc(self, "musicplayer/music#")
        factory.forwarder = self


musicplayer = MusicPlayer()

if __name__ == '__main__':
    username = sys.argv[1]
    password = sys.argv[2]

    if musicplayer.login(username, password):
        factory = WampServerFactory("ws://localhost:9000")
        factory.protocol = RpcServerProtocol
        listenWS(factory)

        root = static.File("web/")
        site = server.Site(root)
        reactor.listenTCP(8080, site)
        reactor.run()
    else:
        print "login failed"
