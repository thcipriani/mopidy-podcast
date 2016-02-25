from __future__ import unicode_literals

import datetime

from mopidy.models import Image, ValidatedImmutableObject, fields


class Enclosure(ValidatedImmutableObject):
    """Mopidy model type to represent an episode's media object."""

    # TODO: restrict type to {'application/pdf', 'audio/mpeg', 'audio/x-m4a',
    # 'document/x-epub', 'video/mp4', 'video/quicktime', 'video/x-m4v'}?

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
    """For podcasts distributed as RSS feeds, the podcast's URI is the
    URL from which the RSS feed can be retrieved.

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


class Term(ValidatedImmutableObject):
    """Mopidy model type to represent a search term."""

    field = fields.Field(type=fields.Field)
    """The search term's field or :class:`None`."""

    values = fields.Collection(type=basestring, container=frozenset)
    """The search terms's set of values."""


class Query(ValidatedImmutableObject):
    """Mopidy model type to represent a search query."""

    terms = fields.Collection(type=Term, container=tuple)
    """The query's terms."""

    exact = fields.Field(type=bool, default=False)
    """Indicates an exact query."""
