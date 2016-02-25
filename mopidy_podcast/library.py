from __future__ import unicode_literals

import collections
import itertools
import logging

from mopidy import backend, models

import uritools

from . import Extension, schema, translator

logger = logging.getLogger(__name__)


class PodcastLibraryProvider(backend.LibraryProvider):

    root_directory = models.Ref.directory(uri='podcast:', name='Podcasts')

    def __init__(self, dbpath, config, backend):
        super(PodcastLibraryProvider, self).__init__(backend)
        ext_config = config[Extension.ext_name]
        self.__dbpath = dbpath  # TODO: pass connection?
        self.__reverse_browse = ext_config['browse_order'] == 'desc'
        self.__reverse_lookup = ext_config['lookup_order'] == 'desc'
        self.__search_limit = ext_config['search_limit']
        self.__tracks = {}  # track cache for faster lookup

    def browse(self, uri):
        if uri == self.root_directory.uri:
            refs = self.__list()
        else:
            refs = self.__browse(uri)
        return list(refs)

    def get_images(self, uris):
        feeds = collections.defaultdict(list)
        for uri in uris:
            feeds[uritools.uridefrag(uri).uri].append(uri)
        result = {}
        for feeduri, uris in feeds.items():
            try:
                images = self.__images(feeduri)
            except Exception as e:
                logger.error('Error retrieving images for %s: %s', feeduri, e)
            else:
                result.update((uri, images.get(uri)) for uri in uris)
        return result

    def lookup(self, uri):
        # pop from __tracks, since we don't want cached items to live too long
        try:
            return self.__tracks.pop(uri)
        except KeyError:
            logger.debug('Lookup cache miss: %s', uri)
        try:
            self.__tracks = tracks = self.__lookup(uritools.uridefrag(uri).uri)
        except Exception as e:
            logger.error('Lookup failed for %s: %s', uri, e)
        else:
            return tracks.pop(uri, [])

    def refresh(self, uri=None):
        # TODO: refresh by uri?
        self.backend.podcasts.clear()
        self.backend.indexer.proxy().refresh()
        self.__tracks.clear()

    def search(self, query=None, uris=None, exact=False):
        # sanitize uris
        uris = frozenset(uris or []).difference([self.root_directory.uri])
        # translate query to model
        try:
            query = translator.query(query, uris, exact)
        except NotImplementedError as e:
            logger.info('Not searching %s: %s', Extension.dist_name, e)
        else:
            return self.__search(query)

    def __browse(self, uri):
        podcast = self.__podcast(uri)
        # TODO: prepare self.__tracks for lookup requests (order!)
        for track in translator.tracks(podcast, reverse=self.__reverse_browse):
            yield models.Ref.track(uri=track.uri, name=track.name)

    def __images(self, uri):
        podcast = self.__podcast(uri)
        # return result dict as with LibraryController.images(uris)
        result = dict(translator.images(podcast))
        result[uri] = [podcast.image] if podcast.image else None
        return result

    def __list(self):
        with schema.connect(self.__dbpath) as connection:
            rows = schema.list(connection)
        return itertools.starmap(translator.ref, rows)

    def __lookup(self, uri):
        podcast = self.__podcast(uri)
        # return result dict as with LibraryController.lookup(uris)
        result = {uri: []}
        for track in translator.tracks(podcast, reverse=self.__reverse_lookup):
            result[track.uri] = [track]
            result[uri].append(track)
        return result

    def __podcast(self, uri):
        scheme, _, feedurl = uri.partition('+')
        assert feedurl and scheme == Extension.ext_name
        return self.backend.podcasts[feedurl]

    def __search(self, query):
        with schema.connect(self.__dbpath) as connection:
            rows = schema.search(connection, query)  # TODO: limit
        albums = []
        tracks = []
        # TODO: retrieve podcasts first, or sort by uri
        # TODO: do not return tracks if album is already included?
        for ref in itertools.starmap(translator.ref, rows):
            try:
                if ref.type == models.Ref.ALBUM:
                    albums.append(translator.album(self.__podcast(ref.uri)))
                elif ref.type == models.Ref.TRACK:
                    tracks.extend(self.lookup(ref.uri))
                else:
                    logger.error('Invalid search result type: %s', ref.type)
            except Exception as e:
                logger.error('Error retrieving %s: %s', ref.uri, e)
        return models.SearchResult(albums=albums, tracks=tracks)
