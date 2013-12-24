__author__ = 'daniel michels'

import json
import sys
import random


from enum import Enum
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


class PlayType(Enum):
    """ Describes the order in which the Playlist returns the tracks to play.

    """
    LINEAR = 1      # Linear order
    SHUFFLE = 2     # Shuffle


class MusicPlayer(object):

    def __init__(self):
        self.playlist = []                  # Array of all tracks
        self.playlist_id = 0                # Id of playlist
        self.current_track_index = 0        # Index of current song
        self.player = Player()              # MPlayer instance
        self.webclient = Webclient()        # Client for WebInterface
        self.mobileclient = Mobileclient()  # Client for MobileInterface
        self.timer = None                   # Timer to start next track
        self.deviceid = 0                   # DeviceId to use
        self.playtype = PlayType.LINEAR     # LINEAR or SHUFFLE

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

    def load_playlist(self, playlist_name):
        # Load playlist
        for playlist in self.mobileclient.get_all_user_playlist_contents():
            if playlist['name'] == playlist_name:
                for track_obj in playlist['tracks']:
                    track_obj['track']['id'] = track_obj['id']
                    self.playlist.append(track_obj['track'])

                # Set playlist_id
                self.playlist_id = playlist['id']
                break;

        # If playlist has not been found, create it
        if self.playlist_id == 0:
            self.playlist_id = self.mobileclient.create_playlist(playlist_name)

    def add_track_to_playlist(self, track):
        """ Append a track to the end of playlist

        Keyword arguments:
        track -- a dictionary containing the track informations

        """
        track_id = self.mobileclient.add_songs_to_playlist(self.playlist_id, track['nid'])[0]
        track['id'] = track_id
        self.playlist.append(track)

        # Notify all clients about the new track
        factory.forwarder.dispatch(PLAYLIST_EVENT_TRACK_ADDED, json.dumps(track))

    def remove_track_from_playlist(self, track_id):
        """ Removes a track from the playlist

        Keyword arguments:
        track_id -- The id of the track to remove

        """
        self.mobileclient.remove_entries_from_playlist(track_id)

        index_to_remove = self._find_index_of_track_id(track_id)

        del self.playlist[index_to_remove]

        factory.forwarder.dispatch(PLAYLIST_EVENT_TRACK_REMOVED, track_id)

    def play_track(self, track_id):
        """ Play a track

        Keyword arguments:
        track_id -- Id of the track to play

        """

        index_of_track = self._find_index_of_track_id(track_id)

        track_to_play = self.playlist[index_of_track]

        if track_to_play is not None:
            # Request stream url from google music
            stream_url = self.mobileclient.get_stream_url(track_to_play["storeId"], self.deviceid)

            # Load stream url to mplayer
            self.player.loadfile(stream_url)

            # For some reason OSX needs to unpause mplayer
            if sys.platform == "darwin":
                self.player.pause()

            # Set track
            self.current_track_index = index_of_track

            # Cancel previous timer
            if self.timer is not None:
                self.timer.cancel()

            # How many minutes does the track last
            track_duration = long(track_to_play["durationMillis"]) / 1000

            # Set Timer to play next track when trackDuration is over
            self.timer = Timer(track_duration, self.play_next_track)
            self.timer.daemon = True
            self.timer.start()

            print "playing", track_to_play["artist"], " - ", track_to_play["title"], " : ", stream_url

            # Fire event that a new track is playing
            factory.forwarder.dispatch(TRACK_EVENT_PLAYBACK, json.dumps(track_to_play))

            return True
        else:
            return False

    def play_next_track(self):
        """ Play the next track in the playlist.

        Returns:
        True or False

        """

        if self.playtype == PlayType.LINEAR:
            # Index of next track to play
            next_track_index = self.current_track_index + 1

            # Restart at index 0 if end of playlist is reached
            if next_track_index >= len(self.playlist):
                next_track_index = 0

        elif self.playtype == PlayType.SHUFFLE:
            # Index of next track to play at random
            next_track_index = random.randrange(0, len(self.playlist), 1)

        # Obtain the id of the next track to play
        next_track_id = self.playlist[next_track_index]['id']

        # Play track with that id
        return self.play_track(next_track_id)

    def play_previous_track(self):
        """ Play the previous track in the playlist.

        Returns:
        True or False

        """

        if self.playtype == PlayType.LINEAR:
            # Index of previous track to play
            previous_track_index = self.current_track_index - 1

            # Contiune from the end of the playlist
            if previous_track_index <= 0:
                previous_track_index = len(self.playlist) - 1

        elif self.playtype == PlayType.SHUFFLE:
            # Index of the previous track is random
            previous_track_index = random.randrange(0, len(self.playlist), 1)

        # Obtain the id of the previous track to play
        previous_track_id = self.playlist[previous_track_index]['id']

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
        current_track_id = self.playlist[self.current_track_index]
        return self.play_track(current_track_id)

    def _find_index_of_track_id(self, track_id):
        index = 0

        for track in self.playlist:
            if track['id'] == track_id:
                return index
            index += 1

        return None


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
        return json.dumps(musicplayer.playlist)

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

        status['playtype'] = musicplayer.playtype

        return json.dumps(status)

    @exportRpc
    def add_to_playlist(self, track_json):
        # Convert Json to dictionary
        track = json.loads(track_json)

        # Append track to playlist
        musicplayer.add_track_to_playlist(track)

    @exportRpc
    def remove_from_playlist(self, track_id):
        return musicplayer.remove_track_from_playlist(track_id)

    @exportRpc
    def set_playtype(self, playtype):
        musicplayer.playtype = playtype
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
    if len(sys.argv) <= 3:
        print "Usage: Musicplayer.py <username> <password> <playlist_name>"
        exit()

    username = sys.argv[1]
    password = sys.argv[2]
    playlist_name = sys.argv[3]

    if musicplayer.login(username, password):
        musicplayer.load_playlist(playlist_name)

        factory = WampServerFactory("ws://localhost:9000")
        factory.protocol = RpcServerProtocol
        listenWS(factory)

        root = static.File("web/")
        site = server.Site(root)
        reactor.listenTCP(8080, site)
        reactor.run()
    else:
        print "login failed"
