from __future__ import unicode_literals

import collections
import itertools
import logging
import operator

from mopidy import backend, models

import uritools

from . import Extension, schema, translator

logger = logging.getLogger(__name__)


class PodcastLibraryProvider(backend.LibraryProvider):

    root_directory = models.Ref.directory(uri='podcast:', name='Podcasts')

    def __init__(self, dbpath, config, backend):
        super(PodcastLibraryProvider, self).__init__(backend)
        ext_config = config[Extension.ext_name]
        self.__dbpath = dbpath
        self.__reverse_browse = ext_config['browse_order'] == 'desc'
        self.__search_limit = ext_config['search_limit']
        self.__timeout = ext_config['timeout']
        self.__tracks = {}  # track cache for faster lookup

    def browse(self, uri):
        if uri == self.root_directory.uri:
            with self.__connect() as connection:
                rows = schema.list(connection)
            refs = itertools.starmap(translator.ref, rows)
        else:
            tracks = self.__tracks = translator.tracks(self.__podcast(uri))
            uris = list(reversed(tracks) if self.__reverse_browse else tracks)
            refs = (models.Ref.track(uri=uri, name=tracks[uri].name)
                    for uri in uris)
        return list(refs)

    def get_distinct(self, field, query):
        try:
            expr = translator.field(field)
        except NotImplementedError:
            return []
        try:
            params = translator.query(query)
        except NotImplementedError:
            return []
        with schema.connect(self.__dbpath) as connection:
            rows = schema.distinct(connection, expr, **params)
        return [row[0] for row in rows]

    def get_images(self, uris):
        podcasts = collections.defaultdict(list)
        for uri in uris:
            podcasts[uritools.uridefrag(uri).uri].append(uri)
        result = {}
        for uri, uris in podcasts.items():
            try:
                images = translator.images(self.__podcast(uri))
            except Exception as e:
                logger.warning('Cannot retrieve images for %s: %s', uri, e)
            else:
                result.update((uri, images.get(uri)) for uri in uris)
        return result

    def lookup(self, uri):
        # pop from __tracks since we don't want cached tracks to live too long
        try:
            track = self.__tracks.pop(uri)
        except KeyError:
            logger.debug('Lookup cache miss: %s', uri)
        else:
            return [track]
        try:
            absuri, fragment = uritools.uridefrag(uri)
            self.__tracks = tracks = translator.tracks(self.__podcast(absuri))
            result = [self.__tracks.pop(uri)] if fragment else tracks.values()
        except LookupError:
            logger.warning('Lookup error for %s', uri)
        except Exception as e:
            logger.warning('Lookup error for %s: %s', uri, e)
        else:
            return list(result)

    def refresh(self, uri=None):
        # TODO: refresh by uri?
        self.backend.podcasts.clear()
        self.backend.indexer.proxy().refresh()
        self.__tracks.clear()

    def search(self, query=None, uris=None, exact=False):
        # convert query to schema parameters
        try:
            params = translator.query(query, exact)
        except NotImplementedError:
            return None  # query not supported
        # sanitize uris
        uris = frozenset(uris or []).difference([self.root_directory.uri])
        # combine search results for multiple uris
        refs = []
        for uri in uris or [None]:
            if self.__search_limit is None:
                limit = None
            else:
                limit = self.__search_limit - len(refs)
            try:
                result = self.__search(uri, exact, limit=limit, **params)
            except Exception as e:
                logger.error('Error searching %s: %s', Extension.ext_name, e)
            else:
                refs.extend(result)
        # convert refs to models; sort on URI for (more) efficient track lookup
        # TODO: merge translator.tracks(podcast) for all podcasts in refs?
        results = {}
        for ref in sorted(refs, key=operator.attrgetter('uri')):
            try:
                if ref.type == models.Ref.ALBUM:
                    model = translator.album(self.__podcast(ref.uri))
                elif ref.type == models.Ref.TRACK:
                    model, = self.lookup(ref.uri)
                else:
                    logger.error('Invalid podcast result type "%s"', ref.type)
            except Exception as e:
                logger.warning('Error retrieving %s: %s', ref.uri, e)
            else:
                results[ref.uri] = model
        # convert to search result model; keep original result order
        albums = []
        tracks = []
        for model in (results[ref.uri] for ref in refs if ref.uri in results):
            if isinstance(model, models.Album):
                albums.append(model)
            elif isinstance(model, models.Track):
                tracks.append(model)
            else:
                raise TypeError('Invalid model type')
        return models.SearchResult(albums=albums, tracks=tracks)

    def __connect(self):
        return schema.connect(self.__dbpath, timeout=self.__timeout)

    def __podcast(self, uri):
        scheme, _, feedurl = uri.partition('+')
        assert feedurl and scheme == Extension.ext_name
        return self.backend.podcasts[feedurl]

    def __search(self, uri, exact, **params):
        if uri is not None:
            scheme, _, feedurl = uri.partition('+')
            assert feedurl and scheme == Extension.ext_name
        else:
            feedurl = None
        with schema.connect(self.__dbpath) as connection:
            if exact:
                rows = schema.search(connection, uri=feedurl, **params)
            else:
                rows = schema.ftsearch(connection, uri=feedurl, **params)
        return itertools.starmap(translator.ref, rows)
