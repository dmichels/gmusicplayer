// WebSocket Session
var session;

// Id of current Track
var currentTrackId;

var PLAYTYPE_LINEAR = 1;
var PLAYTYPE_SHUFFLE = 2;

$(document).ready(function() {
	// WAMP server
	var wsuri = "ws://" + document.location.hostname +":9000";

	// Click on play track in playlist table
	$('#playlistTable').on('click', "a[class='play_track']", function() {
		// Find the parent row of this link
		var row = $(this).parents("tr");

		// Extract track id
		var trackId = row.data('id');

		playTrack(trackId);
	});

	// Click on remove track in playlist table
	$('#playlistTable').on('click', "a[class='remove_track']", function() {
		// Find the parent row of this link
		var row = $(this).parents("tr");

		// Extract track id
		var trackId = row.data('id');

		removeTrackFromPlaylist(trackId);
	});

	// Click on add to playlist
	$('#searchResultTable').on('click', "a[class='add_to_playlist']", function() {
		// Find the parent row of this link
		var row = $(this).parents("tr");

		// Extract track Json
		var trackJson = row.data('value');

		addToPlaylist(trackJson);
	});

	// Search for tracks
	$('#searchBox').submit(function(event) {
		event.preventDefault();
		var query = $('#queryBox').val();

		$('#searchResults').removeClass("hidden");
		$('#index').addClass("hidden");

		$('#searchResultTable').addClass("hidden");
		$('#loadingAnimation').removeClass("hidden");
		
		search(query, function(res){
			var resultArray = $.parseJSON( res );
		
			$('#searchResultTable > tbody').empty();

			$.each(resultArray, function(index, value) {
				var track = value.track;

				$('#searchResultTable > tbody').append("<tr data-value='" + JSON.stringify(track) + "'>"
				+ "<td style='vertical-align:middle'><img src='" + track.albumArtRef[0].url + "' style='width: 34px; height: 34px'/></td>"
				+ "<td style='vertical-align:middle'>" + track.artist + "</td>"
				+ "<td style='vertical-align:middle'>" + track.title + "</td>"
				+ "<td style='vertical-align:middle'>" + track.album + "</td>"
				+ "<td style='vertical-align:middle'><a href='#' class='add_to_playlist'><span class='glyphicon glyphicon-plus'></span></a></td>"
				+ "</tr>");
			});

			$('#searchResultTable').removeClass("hidden");
			$('#loadingAnimation').addClass("hidden");

		}, function(res){
			console.log("error");
		});
	});

	ab.connect(wsuri,

		// WAMP session was established
		function (s) {
			session = s;
 		
 			// Subscribe to newtrack events that get fired when a new Track is added to the Playlist
 			s.subscribe("musicplayer/playlist/events/track_added_to_playlist", function(topicUri, trackJson) {
 				var track = $.parseJSON(trackJson);

 				handleEvent_TrackAddedToPlaylist(track);
 			});

 			// Subscribe to track removed from playlist
 			s.subscribe("musicplayer/playlist/events/track_removed_from_playlist", function(topicUri, trackId) {
				handleEvent_TrackRemovedFromPlaylist(trackId);
 			});

 			// Subscribe to playtype changed events
 			s.subscribe("musicplayer/playlist/events/playtype_changed", function(topicUri, playtype) {
 				handleEvent_PlaytypeChanged(playtype);
 			});

 			// Subscribe to playingtrack events that get fired when a Track starts playing
 			s.subscribe("musicplayer/events/playback", function(topicUri, trackJson) {
 				var track = $.parseJSON(trackJson);

 				handleEvent_TrackPlayback(track)
 			});

 			// Get Status from Server
 			s.call("musicplayer/music#get_status").then(function(statusJson) {
 				var status = $.parseJSON(statusJson);

 				handleEvent_TrackPlayback(status.currentTrack);
 				handleEvent_PlaytypeChanged(status.playtype);
			});
 	
 			// Initialy load Playlist from server	
 			loadPlaylist();
 		},

		// WAMP session is gone
		function (code, reason) {
			console.log(reason);
		}
	);
});

/**
 *	Removes the table row that displays the track from the playlistTable
 *
 *	@method	handleEvent_TrackRemovedFromPlaylist
 *	@param {String} The id of the track that has been removed from playlist
 **/
function handleEvent_TrackRemovedFromPlaylist(trackId) {
	try {
		$('#playlistTable > tbody').find("[data-id='" + trackId + "']").remove();
	} catch (exception) {
		console.log(exception);
	}
}

/**
 *	Adds a Track to the playlistTable.
 *
 *	@method handleEvent_TrackAddedToPlaylist
 *	@param {Object} The track that has been added to playlist
 **/
function handleEvent_TrackAddedToPlaylist(track) {
	try {
		$('#playlistTable > tbody').append("<tr data-id='" + track.nid + "'>"
			+ "<td style='vertical-align:middle'><a href='#'><img class='albumArt' src='" + track.albumArtRef[0].url + "'/></a></td>"
			+ "<td style='vertical-align:middle'>" + track.artist + "</td>"
			+ "<td style='vertical-align:middle'>" + track.title + "</td>"
			+ "<td style='vertical-align:middle'>" + track.album + "</td>"
			+ "<td style='vertical-align:middle'><a href='#' class='play_track'><i class='glyphicon glyphicon-play'></i></a></td>"
			+ "<td style='vertical-align:middle'><a href='#' class='remove_track'><i class='glyphicon glyphicon-remove-sign'></i></a></td>"
			+ "</tr>");
	} catch (exception) {
		console.log(exception);
	}
}

/**
 * Set new playtype
 *
 * @method handleEvent_PlaytypeChanged
 * @param {Integer} The new playtype
 **/
function handleEvent_PlaytypeChanged(playtype) {
	$('#currentPlaytype').empty();

	if(playtype == PLAYTYPE_LINEAR) {
		$('#currentPlaytype').append("<i class='glyphicon glyphicon-arrow-right'/></i> Linear <b class='caret'></b>");
	} else {
		$('#currentPlaytype').append("<i class='glyphicon glyphicon-random'/></i> Shuffle <b class='caret'></b>");
	}
	
}

/**
 *	Set the track as currently playbacked
 *
 *	@method handleEvent_TrackPlayback
 *	@param {Object} The track that is playing
 **/
function handleEvent_TrackPlayback(track) {
	try {
		var duration = track.durationMillis / 1000;

		var minutes = Math.floor(duration / 60);
		var seconds = duration - (minutes * 60);

		if(seconds < 10) { seconds = "0" + seconds; }


		$('#currentTrack #artist').text(track.artist);
		$('#currentTrack #track').text(track.title);
		$('#currentTrack #album').text(track.album);
		$('#currentTrack #genre').text(track.genre);
		$('#currentTrack #duration').text( minutes + ":" + seconds);
		$('#currentTrack #albumArt').attr("src", track.albumArtRef[0].url);
	} catch (exception) {
		console.log(exception);
	}
}

/**
 *	Load playlist from server and add tracks to playlistTable.
 *
 *	@method loadPlaylist
 **/
function loadPlaylist() {

	// When the call succeds, add all tracks to playlistTable
	function success(playlistJson) {
		var resultArray = $.parseJSON( playlistJson );
 					
		$.each(resultArray, function(index, track) {
			handleEvent_TrackAddedToPlaylist(track);
		});
	}

	// When the call fails show error
	function error(err) {
		console.log(err);
	}

	session.call("musicplayer/music#get_playlist").then(success, error);
}

/**
 *	Play track
 *
 *	@method playTrack
 *	@params {String} Id of the track to play
 **/
function playTrack(trackId) {
	session.call("musicplayer/music#play", trackId);
}

/**
 *	Play the next track in the playlist. Depends on playmode.
 *
 *	@method playNextTrack
 **/
function playNextTrack() {
	session.call("musicplayer/music#play_next_track");
}

/**
 *	Play the previous track in the playlist. Depends on playmode.
 *
 *	@method playNextTrack
 **/
function playPreviousTrack() {
	session.call("musicplayer/music#play_previous_track");
}
 	
/**
 *
 **/		
function search(query, success, error) {
	session.call("musicplayer/music#search", query).then(success, error);
}

/**
 *	Send a message to the server to add a track to the playlist.
 *
 *	@method addToPlayList
 *	@params {Object} Track to add to the playlist
 **/
function addToPlaylist(track) {

	// When call succeeds show an animation notifying the user that the track was added
	function success(result) {
		$('#trackAddedAlert').animate({opacity: 1}, 300, function() {
			$('#trackAddedAlert').delay(2000).animate({opacity: 0}, 300);
		});
	}

	// On error alert
	function error(err) {
		Alert("Error");
	}

	session.call("musicplayer/music#add_to_playlist", JSON.stringify(track)).then(success, error);
}

/**
 *	Send a message to the server to remove a track from the playlist.
 *
 *	@method removeTrackFromPlaylist
 *	@params {Object} Track to add to the playlist
 **/
function removeTrackFromPlaylist(trackId) {
	session.call("musicplayer/music#remove_from_playlist", trackId);
}

/**
 *	Send a message to the server to stop the playback
 *
 *	@method stopPlayback
 **/
function stop() {
	session.call("musicplayer/music#stop");
}

function setPlayType(playtype) {
	session.call("musicplayer/music#set_playtype", playtype);
}

/**
 *	Show index page
 *
 *	@method showIndexPage
 **/
function showIndexPage() {
	$('#index').removeClass("hidden");
	$('#searchResults').addClass("hidden");
	$('#queryBox').val("");
}

