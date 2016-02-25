from __future__ import unicode_literals

import contextlib
import logging
import os
import threading

import cachetools

from mopidy import backend

import pykka

from . import Extension, opml, rss, schema
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
        self.__import_dir = config[Extension.ext_name]['import_dir']
        if self.__import_dir is None:
            # https://github.com/mopidy/mopidy/issues/1466
            try:
                self.__import_dir = Extension.get_config_dir(config)
            except Exception as e:
                logger.error('Cannot create podcast directory: %s', e)
        self.__feeds = frozenset(config[Extension.ext_name]['feeds'])
        self.__opener = Extension.get_url_opener(config)
        self.__timer = threading.Timer(0, self.refresh)  # initial timeout 0
        self.__update_interval = config[Extension.ext_name]['update_interval']
        self.__backend = backend.actor_ref.proxy()
        self.__proxy = self.actor_ref.proxy()

    def on_start(self):
        self.__timer.start()

    def on_stop(self):
        self.__timer.cancel()

    def refresh(self):
        # TODO: guard/lock while refreshing; keep timestamp for logging
        self.__timer = threading.Timer(self.__update_interval, self.refresh)
        logger.info('Refreshing %s', Extension.dist_name)
        feeds = tuple(self.__feeds.union(self.__scan_import_dir()))
        try:
            with schema.connect(self.__dbpath) as connection:
                schema.cleanup(connection, feeds)
        except Exception as e:
            logger.error('Error refreshing %s: %s', Extension.dist_name, e)
        else:
            self.__proxy.update(feeds)
        self.__timer.start()  # try again next time

    def update(self, feeds):
        if feeds:
            head, tail = feeds[0], feeds[1:]
            self.__update(head)
            self.__proxy.update(tail)
        else:
            logger.debug('Refreshing %s done', Extension.dist_name)

    def __update(self, feedurl):
        try:
            podcast = self.__fetch(feedurl)
        except pykka.ActorDeadError as e:
            logger.debug('Stopped while retrieving %s: %s', feedurl, e)
        except Exception as e:
            logger.error('Error retrieving podcast %s: %s', feedurl, e)
        else:
            with schema.connect(self.__dbpath) as connection:
                schema.update(connection, podcast)

    def __fetch(self, feedurl):
        podcasts = self.__backend.podcasts
        podcast = podcasts.get(feedurl).get()
        if podcast is None:
            logger.debug('Retrieving podcast %s', feedurl)
            # running in the background, no timeout necessary
            with contextlib.closing(self.__opener.open(feedurl)) as source:
                podcast = rss.parse(source)
            podcast = podcasts.setdefault(feedurl, podcast).get()
        return podcast

    def __scan_import_dir(self):
        result = []
        for entry in os.listdir(self.__import_dir):
            path = os.path.join(self.__import_dir, entry)
            if not os.path.isfile(path):
                continue
            if not path.endswith(b'.opml'):
                continue
            try:
                feedurls = self.__parse_file(path)
            except Exception as e:
                logger.error('Error parsing %s: %s', path, e)
            else:
                result.extend(feedurls)
        return result

    def __parse_file(self, path):
        with open(path) as fh:
            outlines = opml.parse(fh)
        for outline in outlines:
            if outline.get('type') == 'rss':
                yield outline['xmlUrl']


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
        # create/update database schema on startup to catch errors early
        dbpath = os.path.join(Extension.get_data_dir(config), b'feeds.db')
        with schema.connect(dbpath) as connection:
            schema.init(connection)
        self.library = PodcastLibraryProvider(dbpath, config, backend=self)
        self.playback = PodcastPlaybackProvider(audio=audio, backend=self)
        self.podcasts = PodcastCache(config)
        # passed to PodcastIndexer.start()
        self.__config = config
        self.__dbpath = dbpath

    def on_start(self):
        self.indexer = PodcastIndexer.start(self.__dbpath, self.__config, self)

    def on_stop(self):
        self.indexer.stop()
