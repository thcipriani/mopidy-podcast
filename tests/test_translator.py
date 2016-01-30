from __future__ import unicode_literals

from mopidy_podcast import translator
from mopidy_podcast.models import Podcast


def test_tracks():
    # TODO: fixture for example
    podcast = Podcast(uri='http://example.com/rss', title='Example')
    assert list(translator.tracks(podcast)) == []
