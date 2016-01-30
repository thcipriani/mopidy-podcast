from __future__ import unicode_literals

import operator

from mopidy import models

import uritools

from . import Extension


def trackuri(uri, guid, safe=uritools.SUB_DELIMS+b':@/?'):
    # timeit shows approx. factor 3 difference
    # return uri + uritools.uricompose(fragment=guid)
    return uri + '#' + uritools.uriencode(guid, safe=safe)


def _track(episode, album, **kwargs):
    return models.Track(
        uri=trackuri(album.uri, episode.guid),
        name=episode.title,
        album=album,
        artists=(
            [models.Artist(name=episode.author)]
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


def tracks(podcast, key=operator.attrgetter('pubdate'), reverse=False):
    uri, _ = uritools.uridefrag(Extension.ext_name + '+' + podcast.uri)
    album = models.Album(
        uri=uri,
        name=podcast.title,
        artists=(
            [models.Artist(name=podcast.author)]
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
            yield (trackuri(uri, episode.guid), [episode.image])
        else:
            yield (trackuri(uri, episode.guid), default)
