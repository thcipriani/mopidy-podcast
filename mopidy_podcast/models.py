from __future__ import unicode_literals

import datetime

from mopidy.models import Image, ValidatedImmutableObject, fields


class Enclosure(ValidatedImmutableObject):
    """Mopidy model type to represent an episode's media object."""

    # TODO: restrict type to {'application/pdf', 'audio/mpeg', 'audio/x-m4a',
    # 'document/x-epub', 'video/mp4', 'video/quicktime', 'video/x-m4v'}

    uri = fields.URI()
    """The URI of the media object."""

    length = fields.Integer(min=0)
    """The media object's file size in bytes."""

    type = fields.Identifier()
    """The media object's MIME type, for example :const:`audio/mpeg`."""


class Episode(ValidatedImmutableObject):
    """Mopidy model type to represent a podcast episode."""

    guid = fields.String()
    """A case-sensitive GUID that uniquely identifies the episode."""

    title = fields.String()
    """The episode's title."""

    pubdate = fields.Field(type=datetime.datetime)
    """The episode's publication date as an instance of
    :class:`datetime.datetime`."""

    author = fields.String()
    """The episode author's name."""

    block = fields.Field(type=bool)
    """Prevent an episode from appearing in the directory."""

    image = fields.Field(type=Image)
    """An image to be displayed with the episode as an instance of
    :class:`Image`.

    """

    duration = fields.Field(type=datetime.timedelta)
    """The episode's duration as a :class:`datetime.timedelta`."""

    explicit = fields.Field(type=bool)
    """Indicates whether the episode contains explicit material."""

    order = fields.Integer(min=1)
    """Overrides the default ordering of episodes."""

    description = fields.String()
    """A description of the episode."""

    enclosure = fields.Field(type=Enclosure)
    """The media object, e.g. the audio stream, attached to the episode as
    an instance of :class:`Enclosure`.

    """


class Podcast(ValidatedImmutableObject):
    """Mopidy model type to represent a podcast."""

    uri = fields.URI()
    """The podcast's URI.

    For podcasts distributed as RSS feeds, the podcast's URI is the
    URL from which the RSS feed can be retrieved.

    Podcast URIs *MUST NOT* contain fragment identifiers.

    """

    title = fields.String()
    """The podcast's title."""

    link = fields.URI()
    """The URL of a website corresponding to the podcast."""

    copyright = fields.String()
    """The podcast's copyright notice."""

    language = fields.Identifier()
    """The podcast's ISO two-letter language code."""

    author = fields.String()
    """The podcast author's name."""

    block = fields.Field(type=bool)
    """Prevent a podcast from appearing in the directory."""

    category = fields.String()
    """The main category of the podcast."""

    image = fields.Field(type=Image)
    """An image to be displayed with the podcast as an instance of
    :class:`Image`.

    """

    explicit = fields.Field(type=bool)
    """Indicates whether the podcast contains explicit material."""

    complete = fields.Field(type=bool)
    """Indicates completion of the podcast."""

    newfeedurl = fields.URI()
    """Used to inform of new feed URL location."""

    description = fields.String()
    """A description of the podcast."""

    episodes = fields.Collection(type=Episode, container=tuple)
    """The podcast's episodes as a :class:`tuple` of :class:`Episode`
    instances.

    """

    # TODO: owner w/nested name, email?


class Outline(ValidatedImmutableObject):
    """Mopidy model type to represent an OPML 2.0 outline."""

    INCLUDE = 'include'
    """Constant used for comparison with the :attr:`type` field."""

    LINK = 'link'
    """Constant used for comparison with the :attr:`type` field."""

    RSS = 'rss'
    """Constant used for comparison with the :attr:`type` field."""

    @classmethod
    def include(cls, **kwargs):
        """Create an :class:`Outline` of :attr:`type` :attr:`INCLUDE`."""
        return cls(type=cls.INCLUDE, **kwargs)

    @classmethod
    def link(cls, **kwargs):
        """Create an :class:`Outline` of :attr:`type` :attr:`LINK`."""
        return cls(type=cls.LINK, **kwargs)

    @classmethod
    def rss(cls, **kwargs):
        """Create an :class:`Outline` of :attr:`type` :attr:`RSS`."""
        return cls(type=cls.RSS, **kwargs)

    text = fields.String()
    """The text to be displayed for the outline."""

    type = fields.Identifier()
    """The type of the outline or :class:`None`."""

    created = fields.Field(type=datetime.datetime)
    """The date-time that the outline node was created."""

    category = fields.String()
    """A string of comma-separated slash-delimited category
    strings."""

    description = fields.String()
    """The top-level description element from the feed pointed to."""

    language = fields.Identifier()
    """The top-level language element from the feed pointed to."""

    title = fields.String()
    """The top-level title element from the feed pointed to."""

    uri = fields.URI()
    """The outline's URI."""


class Term(ValidatedImmutableObject):
    """Mopidy model type to represent a search term."""

    PODCAST_TITLE = 'podcast.title'
    """Constant used for comparison with the :attr:`attribute` field."""

    EPISODE_TITLE = 'episode.title'
    """Constant used for comparison with the :attr:`attribute` field."""

    PODCAST_AUTHOR = 'podcast.author'
    """Constant used for comparison with the :attr:`attribute` field."""

    EPISODE_AUTHOR = 'episode.author'
    """Constant used for comparison with the :attr:`attribute` field."""

    CATEGORY = 'category'
    """Constant used for comparison with the :attr:`attribute` field."""

    PUBDATE = 'pubdate'
    """Constant used for comparison with the :attr:`attribute` field."""

    DESCRIPTION = 'description'
    """Constant used for comparison with the :attr:`attribute` field."""

    attribute = fields.Field(type=basestring, choices=[
        PODCAST_TITLE, EPISODE_TITLE, PODCAST_AUTHOR, EPISODE_AUTHOR,
        CATEGORY, PUBDATE, DESCRIPTION
    ])
    """The search term's attribute or :class:`None`."""

    values = fields.Collection(type=basestring, container=frozenset)
    """The search terms's set of values."""


class Query(ValidatedImmutableObject):
    """Mopidy model type to represent a search query."""

    terms = fields.Collection(type=Term, container=tuple)
    """The query's terms."""

    exact = fields.Field(type=bool, default=False)
    """Indicates an exact query."""
