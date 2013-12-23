__author__ = 'daniel'

import random
import shelve
from enum import Enum


class PlayType(Enum):
    """ Describes the order in which the Playlist returns the tracks to play.

    """
    LINEAR = 1      # Linear order
    SHUFFLE = 2     # Shuffle


class Playlist(object):

    def __init__(self):
        self.track_map = dict()
        self.track_list = []
        self.current_track_index = 0
        self.playtype = PlayType.LINEAR

    def set_playtype(self, playtype):
        self.playtype = playtype

    def get_playtype(self):
        return self.playtype

    def get_tracks(self):
        """ Get a list of all tracks

        Returns:
        A list of all tracks

        """
        rlist = []

        for track_id in self.track_list:
            rlist.append(self.get_track(track_id))

        return rlist

    def get_track(self, track_id):
        """ Get the track with the given id.

        Keywords:
        track_id -- ID of track

        Returns:
        Track or None if track hasn't been found

        """
        return self.track_map[track_id]

    def set_current_track(self, track_id):
        """ Set the current_track_index to the position of the track in playlist

        Returns:
        True if successful else False

        """
        index = self._find_track_position(track_id)

        if index is not None:
            self.current_track_index = index
            return True

        return False

    def get_current_track_id(self):
        """ Get the current track

        """
        current_track_id = self.track_list[self.current_track_index]

        return current_track_id

    def get_next_track_id(self):
        """ Get the next track to play. If playtype is PlayType.LINEAR the if of next track in the playlist is returned.
        If playtype is PlayType.SHUFFLE a random id is returned.

        Returns:
        Id of next track to play.

        """
        next_track_index = None

        if self.playtype == PlayType.LINEAR:
            # PlayType.LINEAR goes one by one through the playlist
            next_track_index = self.current_track_index + 1

            # Restart from the start if end is reached
            if next_track_index >= len(self.track_list):
                next_track_index = 0

        elif self.playtype == PlayType.SHUFFLE:
            # PlayType.SHUFFLE selects the next track at random
            next_track_index = random.randrange(0, len(self.track_list), 1)
            pass

        next_track_id = self.track_list[next_track_index]

        return next_track_id

    def get_previous_track_id(self):
        """ Get the id of the previous track to play. If it's in SHUFFLE mode the previous track will be random.

        Returns:
        Id of previous track
        """
        previous_track_index = None

        if self.playtype == PlayType.LINEAR:
            # PlayType.LINEAR goes through the playlist one by one
            previous_track_index = self.current_track_index - 1

            # If lower then 0 start from the tail of playlist
            if previous_track_index < 0:
                previous_track_index = len(self.track_list) - 1
        elif self.playtype == PlayType.SHUFFLE:
            # PlayType.SHUFFLE select the previous track at random
            previous_track_index = random.randrange(0, len(self.track_list), 1)

        previous_track_id = self.track_list[previous_track_index]

        return previous_track_id

    def add_track(self, track):
        """ Add a track to the end of the playlist. Every track can only be added once.

        Keywords:
        track -- The track to add

        Returns:
        True if track has been added, else False.

        """
        track_id = track['nid']

        if self.track_map.has_key(track_id):
            return False

        # Add track with track_id as key to map
        self.track_map[track_id] = track

        # Add track_id to list
        self.track_list.append(track_id)

        return True

    def remove_track(self, track_id):
        """ Remove track from playlist

        """

        # Obtain index of track
        index = self._find_track_position(track_id)

        if index is not None:
            # Remove track from list
            self.track_list.pop(index)

            # Remove track from map
            self.track_map.pop(track_id, None)

            return True

        return False

    def _find_track_position(self, track_id):
        """ Find position of track in track_list

        """
        for n in range(0, len(self.track_list)):
            if self.track_list[n] == track_id:
                return n

        return None