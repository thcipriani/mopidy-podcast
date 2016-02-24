from __future__ import unicode_literals

import contextlib
import logging
import os
import threading

import cachetools

from mopidy import backend

import pykka

from . import Extension, rss, schema
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


class PodcastIndexer(pykka.ThreadingActor):

    def __init__(self, dbpath, config, backend):
        super(PodcastIndexer, self).__init__()
        self.__dbpath = dbpath
        self.__opener = Extension.get_url_opener(config)
        self.__feeds = config[Extension.ext_name]['feeds']
        self.__interval = config[Extension.ext_name]['update_interval']
        self.__timer = threading.Timer(self.__interval, self.__timeout)
        self.__backend = backend.actor_ref.proxy()
        self.__proxy = self.actor_ref.proxy()

    def on_start(self):
        self.__proxy.refresh()
        self.__timer.start()

    def on_stop(self):
        self.__timer.cancel()

    def refresh(self, uris=None):
        # TODO: delete everything but configured feeds if config changed
        if uris is None:
            logger.info('Refreshing %s', Extension.dist_name)
            self.__proxy.refresh(self.__feeds)
        elif uris:
            try:
                self.__update(uris[0])
            except Exception:
                logger.exception('Error refreshing %s' % uris[0])
            self.__proxy.refresh(uris[1:])
        else:
            logger.debug('Refreshing %s done', Extension.dist_name)

    def __timeout(self):
        self.__timer = threading.Timer(self.__interval, self.__timeout)
        self.__proxy.refresh()
        self.__timer.start()

    def __update(self, feedurl):
        # do *not* block backend for retrieving/updating podcast
        podcasts = self.__backend.podcasts
        podcast = podcasts.get(feedurl).get()
        if podcast is None:
            logger.debug('Retrieving podcast %s', feedurl)
            # running in the background, no timeout necessary
            with contextlib.closing(self.__opener.open(feedurl)) as source:
                podcast = rss.parse(source)
            podcast = podcasts.setdefault(feedurl, podcast).get()
        logger.debug('Updating podcast %s', podcast.uri)
        with schema.connect(self.__dbpath) as connection:
            schema.update(connection, podcast)


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
        self.__config = config
        self.__dbpath = dbpath = self.__init_schema(config)
        self.library = PodcastLibraryProvider(dbpath, config, backend=self)
        self.playback = PodcastPlaybackProvider(audio=audio, backend=self)
        self.podcasts = PodcastCache(config)

    def __init_schema(self, config):
        # create/update database schema on startup to catch errors early
        dbpath = os.path.join(Extension.get_data_dir(config), b'feeds.db')
        with schema.connect(dbpath) as connection:
            schema.init(connection)
        return dbpath

    def on_start(self):
        logger.debug('Starting %s update actor', Extension.dist_name)
        self.__update_actor_ref = PodcastIndexer.start(
            self.__dbpath, self.__config, self
        )

    def on_stop(self):
        logger.debug('Stopping %s update actor', Extension.dist_name)
        self.__update_actor_ref.stop()
