from __future__ import unicode_literals

import contextlib
import logging

import cachetools

from mopidy import backend

import pykka

from . import Extension, rss
from .library import PodcastLibraryProvider
from .playback import PodcastPlaybackProvider

logger = logging.getLogger(__name__)


class PodcastCache(cachetools.TTLCache):

    pykka_traversable = True

    def __init__(self, config):
        # TODO: missing deprecated in cachetools v1.2
        super(PodcastCache, self).__init__(
            maxsize=config[Extension.ext_name]['cache_size'],
            ttl=config[Extension.ext_name]['cache_ttl'],
            missing=self.__missing
        )
        self.__opener = Extension.get_url_opener(config)
        self.__timeout = config[Extension.ext_name]['timeout']

    def __missing(self, feedurl):
        logger.debug('Podcast cache miss: %s', feedurl)
        with contextlib.closing(self.__open(feedurl)) as source:
            podcast = rss.parse(source)
        return podcast

    def __open(self, url):
        return self.__opener.open(url, timeout=self.__timeout)


class PodcastBackend(pykka.ThreadingActor, backend.Backend):

    uri_schemes = [
        'podcast',
        'podcast+file',
        'podcast+ftp',
        'podcast+http',
        'podcast+https'
    ]

    def __init__(self, config, audio):
        super(PodcastBackend, self).__init__()
        self.library = PodcastLibraryProvider(config, backend=self)
        self.playback = PodcastPlaybackProvider(audio=audio, backend=self)
        self.podcasts = PodcastCache(config)
