from __future__ import unicode_literals

import logging

from mopidy import backend

import uritools

from . import Extension

logger = logging.getLogger(__name__)


def get_media_uri(podcast, guid):
    # TODO: filter media types, blocked?
    for episode in podcast.episodes:
        if episode.guid == guid and episode.enclosure:
            return episode.enclosure.uri
    logger.warning('No episode found for GUID %s in %s', guid, podcast.uri)
    return None


class PodcastPlaybackProvider(backend.PlaybackProvider):

    def translate_uri(self, uri):
        defrag = uritools.uridefrag(uri)
        scheme, _, feedurl = defrag.uri.partition('+')
        assert scheme == Extension.ext_name
        try:
            podcast = self.backend.podcasts[feedurl]
        except Exception as e:
            logger.error('Error retrieving podcast %s: %s', feedurl, e)
        else:
            return get_media_uri(podcast, defrag.getfragment())
