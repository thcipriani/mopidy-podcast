from __future__ import unicode_literals


def _match(q, value):
    return value and q.lower() in value.lower()


FILTER_FIELDS = {
    'uri',
    'track_name',
    'album',
    'artist',
    'composer',
    'performer',
    'albumartist',
    'track_no',
    'genre',
    'date',
    'comment',
    'any'
}

DEFAULT_FILTERS = dict.fromkeys(FILTER_FIELDS, lambda q, model: False)

# TODO: any
TRACK_FILTERS = [
    dict(
        DEFAULT_FILTERS,
        uri=lambda q, track: _match(q, track.uri),
        track_name=lambda q, track: _match(q, track.name),
        album=lambda q, track: track.album and _match(q, track.album.name),
        artist=lambda q, track: any(
            _match(q, a.name) for a in track.artists
        ),
        composer=lambda q, track: any(
            _match(q, a.name) for a in track.composers
        ),
        performer=lambda q, track: any(
            _match(q, a.name) for a in track.performers
        ),
        albumartist=lambda q, track: track.album and any(
            _match(q, a.name) for a in track.album.artists
        ),
        track_no=lambda q, track: int(q) == track.track_no,
        genre=lambda q, track: _match(q, track.genre),
        date=lambda q, track: track.date and track.date.startswith(q),
        comment=lambda q, track: _match(q, track.comment)
    ),
    dict(
        DEFAULT_FILTERS,
        uri=lambda q, track: q == track.uri,
        track_name=lambda q, track: q == track.name,
        album=lambda q, track: track.album and q == track.album.name,
        artist=lambda q, track: any(
            q == a.name for a in track.artists
        ),
        composer=lambda q, track: any(
            q == a.name for a in track.composers
        ),
        performer=lambda q, track: any(
            q == a.name for a in track.performers
        ),
        albumartist=lambda q, track: track.album and any(
            q == a.name for a in track.album.artists
        ),
        track_no=lambda q, track: int(q) == track.track_no,
        genre=lambda q, track: q == track.genre,
        date=lambda q, track: q == track.date,
        comment=lambda q, track: q == track.comment
    )
]

# TODO: any
ALBUM_FILTERS = [
    dict(DEFAULT_FILTERS,
         uri=lambda q, album: _match(q, album.uri),
         album=lambda q, album: _match(q, album.name),
         artist=lambda q, album: any(
             _match(q, a.name) for a in album.artists
         ),
         albumartist=lambda q, album: any(
             _match(q, a.name) for a in album.artists
         ),
         date=lambda q, album: album.date and album.date.startswith(q)),
    dict(DEFAULT_FILTERS,
         uri=lambda q, album: q == album.uri,
         album=lambda q, album: q == album.name,
         artist=lambda q, album: any(
             q == a.name for a in album.artists
         ),
         albumartist=lambda q, album: any(
             q == a.name for a in album.artists
         ),
         date=lambda q, album: q == album.date)
]

# FIXME: case insensitive 'in', strip q, any, albumartist
ARTIST_FILTERS = [
    dict(
        DEFAULT_FILTERS,
        uri=lambda q, artist: _match(q, artist.uri),
        artist=lambda q, artist: _match(q, artist.name)
    ),
    dict(
        DEFAULT_FILTERS,
        uri=lambda q, artist: q == artist.uri,
        artist=lambda q, artist: q == artist.name
    )
]


def _get_filters(filters, query):
    from functools import partial
    # FIXME: multi-values
    return [partial(filters[f], v) for f, v in query.iteritems()]


def filter_tracks(tracks, query, exact=False):
    filters = _get_filters(TRACK_FILTERS[exact], query)
    return filter(lambda t: all(f(t) for f in filters), tracks)


def filter_albums(albums, query, exact=False):
    filters = _get_filters(ALBUM_FILTERS[exact], query)
    return filter(lambda t: all(f(t) for f in filters), albums)


def filter_artists(artists, query, exact=False):
    filters = _get_filters(ARTIST_FILTERS[exact], query)
    return filter(lambda t: all(f(t) for f in filters), artists)