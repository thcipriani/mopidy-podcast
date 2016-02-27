from __future__ import unicode_literals

import collections
import operator
import re

from mopidy.models import Album, Artist, Ref, Track

import uritools

from . import Extension

_EXPRESSIONS = {
    # field is "track", while search keyword is "track_name"?
    'track': 'episode.title',
    'artist': 'episode.author',
    'albumartist': 'podcast.author',
    'album': 'podcast.title',
    'date': 'date(pubdate)',
    'genre': 'category'
}

_PARAMETERS = {
    'track_name': 'episode_title',
    'album': 'podcast_title',
    'artist': 'episode_author',
    'albumartist': 'podcast_author',
    'genre': 'category',
    'date': 'pubdate',
    'comment': 'description',
    'any': 'any'
}


def _albumuri(feedurl):
    return uritools.uridefrag(Extension.ext_name + '+' + feedurl).uri


def _trackuri(albumuri, guid, safe=uritools.SUB_DELIMS+b':@/?'):
    # timeit shows approx. factor 3 difference
    # return albumuri + uritools.uricompose(fragment=guid)
    return albumuri + '#' + uritools.uriencode(guid, safe=safe)


def ref(feedurl, title, guid=None, *args):
    uri = _albumuri(feedurl)
    if guid:
        return Ref.track(uri=_trackuri(uri, guid), name=title)
    else:
        return Ref.album(uri=uri, name=title)


def album(podcast):
    return Album(
        uri=_albumuri(podcast.uri),
        name=podcast.title,
        artists=([Artist(name=podcast.author)] if podcast.author else None),
        num_tracks=len(podcast.episodes)
    )


def tracks(podcast, key=operator.attrgetter('pubdate'), _album=album):
    album = _album(podcast)
    result = collections.OrderedDict()
    # TODO: support <itunes:order>
    for index, episode in enumerate(sorted(podcast.episodes, key=key), 1):
        # TODO: filter by block/explicit/media type?
        if not episode.guid:
            continue
        if not episode.enclosure or not episode.enclosure.uri:
            continue
        uri = _trackuri(album.uri, episode.guid)
        result[uri] = Track(
            uri=uri,
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
            genre=podcast.category,
            track_no=index
        )
    return result


def images(podcast):
    uri = _albumuri(podcast.uri)
    default = [podcast.image] if podcast.image else []
    result = {uri: default}
    for episode in podcast.episodes:
        if episode.image:
            images = [episode.image] + default
        else:
            images = default
        result[_trackuri(uri, episode.guid)] = images
    return result


def field(name):
    try:
        expr = _EXPRESSIONS[name]
    except KeyError:
        raise NotImplementedError('Field "%s" not supported' % name)
    else:
        return expr


def query(query, exact=True, re=re.compile(r'["^*]')):
    params = {}
    for key, values in query.items():
        if exact:
            value = ''.join(values)  # FIXME: multi-valued exact queries?
        else:
            value = ' '.join('"%s"' % re.sub(' ', v) for v in values)
        try:
            name = _PARAMETERS[key]
        except KeyError:
            raise NotImplementedError('Search field "%s" not supported' % key)
        else:
            params[name] = value
    return params
