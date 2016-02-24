from __future__ import unicode_literals

import operator

from mopidy.models import Album, Artist, Ref, Track

import uritools

from . import Extension, models

_FIELDS = {
   'any': None,
   'album': models.Podcast.title,
   'albumartist': models.Podcast.author,
   'artist': models.Episode.author,
   'comment': models.Episode.description,
   'date': models.Episode.pubdate,
   'genre': models.Podcast.category,
   'track_name': models.Episode.title
}


def _trackuri(uri, guid, safe=uritools.SUB_DELIMS+b':@/?'):
    # timeit shows approx. factor 3 difference
    # return uri + uritools.uricompose(fragment=guid)
    return uri + '#' + uritools.uriencode(guid, safe=safe)


def _track(episode, album, **kwargs):
    return Track(
        uri=_trackuri(album.uri, episode.guid),
        name=episode.title,
        album=album,
        artists=(
            [Artist(name=episode.author)]
            if episode.author
            else None
        ),
        date=(
            episode.pubdate.date().isoformat()
            if episode.pubdate
            else None
        ),
        length=(
            int(episode.duration.total_seconds() * 1000)
            if episode.duration
            else None
        ),
        comment=episode.description,
        **kwargs
    )


def ref(feedurl, title, guid=None):
    uri, _ = uritools.uridefrag(Extension.ext_name + '+' + feedurl)
    if guid:
        return Ref.track(uri=_trackuri(uri, guid), name=title)
    else:
        return Ref.album(uri=uri, name=title)


def album(podcast):
    uri, _ = uritools.uridefrag(Extension.ext_name + '+' + podcast.uri)
    return Album(
        uri=uri,
        name=podcast.title,
        artists=(
            [Artist(name=podcast.author)]
            if podcast.author
            else None
        ),
        num_tracks=len(podcast.episodes)
    )


def tracks(podcast, key=operator.attrgetter('pubdate'), reverse=False):
    uri, _ = uritools.uridefrag(Extension.ext_name + '+' + podcast.uri)
    album = Album(
        uri=uri,
        name=podcast.title,
        artists=(
            [Artist(name=podcast.author)]
            if podcast.author
            else None
        ),
        num_tracks=len(podcast.episodes)
    )
    genre = podcast.category
    # TODO: support <itunes:order>?
    episodes = sorted(podcast.episodes, key=key, reverse=reverse)
    for index, episode in enumerate(episodes, start=1):
        # TODO: filter block/media type?
        if episode.enclosure and episode.enclosure.uri:
            yield _track(episode, album=album, genre=genre, track_no=index)


def images(podcast):
    uri, _ = uritools.uridefrag(Extension.ext_name + '+' + podcast.uri)
    default = [podcast.image] if podcast.image else None
    for episode in podcast.episodes:
        if episode.image:
            yield (_trackuri(uri, episode.guid), [episode.image])
        else:
            yield (_trackuri(uri, episode.guid), default)


def query(query, uris, exact=False):
    # TODO: uris
    terms = []
    for key, values in query.items():
        try:
            field = _FIELDS[key]
        except KeyError:
            raise NotImplementedError('Search key "%s" not supported' % key)
        else:
            terms.append(models.Term(field=field, values=values))
    return models.Query(terms=terms, exact=exact)
