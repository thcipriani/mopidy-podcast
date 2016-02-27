from __future__ import unicode_literals

import contextlib
import datetime
import logging
import os
import threading
import xml.etree.ElementTree

import cachetools

from mopidy import backend

import pykka

from . import BackendError, Extension, rss, schema
from .library import PodcastLibraryProvider
from .playback import PodcastPlaybackProvider

logger = logging.getLogger(__name__)


def parse_opml(path):
    # http://dev.opml.org/spec2.html
    root = xml.etree.ElementTree.parse(path).getroot()
    for e in root.findall('./body//outline[@type="rss"]'):
        url = e.get('xmlUrl')
        if url:
            yield url
        else:
            logger.warning('Found RSS outline without xmlUrl in %s', path)


def stream(session, url, **kwargs):
    response = session.get(url, stream=True, **kwargs)
    response.raise_for_status()
    response.raw.decode_content = True
    return contextlib.closing(response)


class PodcastCache(cachetools.TTLCache):

    pykka_traversable = True

    def __init__(self, config):
        # TODO: "missing" parameter will be deprecated in cachetools v1.2
        super(PodcastCache, self).__init__(
            maxsize=config[Extension.ext_name]['cache_size'],
            ttl=config[Extension.ext_name]['cache_ttl'],
            missing=self.__missing
        )
        self.__session = Extension.get_requests_session(config)
        self.__timeout = config[Extension.ext_name]['timeout']

    def __missing(self, url):
        with stream(self.__session, url, timeout=self.__timeout) as r:
            podcast = rss.parse(r.raw, url)
        logger.debug('Retrieving %s took %s', url, r.elapsed)
        return podcast


class PodcastUpdateActor(pykka.ThreadingActor):

    def __init__(self, dbpath, config, backend):
        super(PodcastUpdateActor, self).__init__()
        self.__dbpath = dbpath
        self.__backend = backend.actor_ref.proxy()
        self.__import_dir = config[Extension.ext_name]['import_dir']
        if self.__import_dir is None:
            # https://github.com/mopidy/mopidy/issues/1466
            try:
                self.__import_dir = Extension.get_config_dir(config)
            except Exception as e:
                logger.error('Cannot create podcast import directory: %s', e)
        self.__feeds = frozenset(config[Extension.ext_name]['feeds'])
        self.__session = Extension.get_requests_session(config)
        self.__timeout = config[Extension.ext_name]['timeout']
        self.__timer = threading.Timer(0, self.refresh)  # initial zero timeout
        self.__update_interval = config[Extension.ext_name]['update_interval']
        self.__update_started = None
        self.__proxy = self.actor_ref.proxy()

    def on_start(self):
        logger.debug('Starting %s', self.__class__.__name__)
        self.__timer.start()

    def on_stop(self):
        logger.debug('Stopping %s', self.__class__.__name__)
        self.__timer.cancel()

    def prepare_update(self, feeds):
        try:
            with schema.connect(self.__dbpath) as connection:
                for uri, _ in schema.list(connection):
                    if uri not in feeds:
                        schema.delete(connection, uri)
        except Exception:
            logger.exception('Error refreshing %s', Extension.dist_name)
            self.__update_started = None
        else:
            self.__proxy.update(feeds)

    def refresh(self):
        timer = self.__timer
        self.__timer = threading.Timer(self.__update_interval, self.refresh)
        timer.cancel()  # in case of manual refresh
        # prevent multiple concurrent updates
        if self.__update_started:
            logger.debug('Already refreshing %s', Extension.dist_name)
        else:
            self.__update_started = datetime.datetime.now()
            feeds = tuple(self.__feeds.union(self.__scan_import_dir()))
            logger.info('Refreshing %d podcast(s)', len(feeds))
            self.__proxy.prepare_update(feeds)
        self.__timer.start()

    def update(self, feeds):
        if feeds:
            head, tail = feeds[0], feeds[1:]
            try:
                self.__update(head)
            except Exception:
                logger.exception('Error refreshing %s', Extension.ext_name)
                self.__update_started = None
            else:
                self.__proxy.update(tail)
        else:
            d = datetime.datetime.now() - self.__update_started
            logger.info('Refreshing %s took %s', Extension.dist_name, d)
            self.__update_started = None

    def __fetch(self, feedurl):
        podcasts = self.__backend.podcasts
        podcast = podcasts.get(feedurl).get()
        if podcast is None:
            # TODO: If-Modified-Since with schema.pubdate(feedurl)?
            with stream(self.__session, feedurl, timeout=self.__timeout) as r:
                podcast = rss.parse(r.raw, feedurl)
            logger.debug('Retrieving %s took %s', feedurl, r.elapsed)
            podcast = podcasts.setdefault(feedurl, podcast).get()
        return podcast

    def __scan_import_dir(self):
        result = []
        for entry in os.listdir(self.__import_dir):
            path = os.path.join(self.__import_dir, entry)
            try:
                if not os.path.isfile(path):
                    continue
                elif path.endswith(b'.opml'):
                    urls = parse_opml(path)
                else:
                    logger.debug('Skipping unknown file %s', path)
            except Exception as e:
                logger.error('Error parsing %s: %s', path, e)
            else:
                result.extend(urls)
        return result

    def __update(self, feedurl):
        try:
            podcast = self.__fetch(feedurl)
        except pykka.ActorDeadError:
            logger.debug('Stopped while retrieving %s', feedurl)
        except Exception as e:
            logger.warning('Cannot update podcast %s: %s', feedurl, e)
        else:
            with schema.connect(self.__dbpath) as connection:
                schema.update(connection, podcast)


class PodcastBackend(pykka.ThreadingActor, backend.Backend):

    uri_schemes = [
        'podcast',
        'podcast+http',
        'podcast+https'
    ]

    def __init__(self, config, audio):
        super(PodcastBackend, self).__init__()
        # create/update database schema on startup to catch errors early
        dbpath = os.path.join(Extension.get_data_dir(config), b'feeds.db')
        try:
            with schema.connect(dbpath) as connection:
                schema.init(connection)
        except Exception as e:
            raise BackendError('Error initializing database: %s' % e)
        self.library = PodcastLibraryProvider(dbpath, config, backend=self)
        self.playback = PodcastPlaybackProvider(audio=audio, backend=self)
        self.podcasts = PodcastCache(config)
        # passed to PodcastUpdateActor.start()
        self.__update_args = [dbpath, config, self]

    def on_start(self):
        self.indexer = PodcastUpdateActor.start(*self.__update_args)

    def on_stop(self):
        self.indexer.stop()
