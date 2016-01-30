from __future__ import unicode_literals

import collections
import logging

from mopidy import backend

import uritools

from . import Extension, translator

logger = logging.getLogger(__name__)


class PodcastLibraryProvider(backend.LibraryProvider):

    # root_directory = models.Ref(uri='podcast:', name='Podcasts')

    def __init__(self, config, backend):
        super(PodcastLibraryProvider, self).__init__(backend)
        ext_config = config[Extension.ext_name]
        self.__reverse_lookup = ext_config['lookup_order'] == 'desc'
        self.__tracks = {}  # track cache for faster lookup

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
        self.__tracks.clear()

    def search(self, query=None, uris=None, exact=False):
        return None

    def __images(self, uri):
        podcast = self.__podcast(uri)
        # return result dict as with LibraryController.images(uris)
        result = dict(translator.images(podcast))
        result[uri] = [podcast.image] if podcast.image else None
        return result

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
