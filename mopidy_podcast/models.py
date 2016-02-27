from __future__ import unicode_literals

from datetime import datetime, timedelta

from mopidy.models import Image, ValidatedImmutableObject, fields


class Enclosure(ValidatedImmutableObject):
    """Mopidy model type to represent an episode's media object."""

    uri = fields.URI()
    """The URI of the media object."""

    length = fields.Integer(min=0)
    """The media object's file size in bytes."""

    # TODO: restrict type to {'application/pdf', 'audio/mpeg', 'audio/x-m4a',
    # 'document/x-epub', 'video/mp4', 'video/quicktime', 'video/x-m4v'}?
    type = fields.Identifier()
    """The media object's MIME type, for example :const:`audio/mpeg`."""


class Episode(ValidatedImmutableObject):
    """Mopidy model type to represent a podcast episode."""

    guid = fields.String()
    """A case-sensitive GUID that uniquely identifies the episode."""

    title = fields.String()
    """The episode's title."""

    # TODO: default necessary for sorting?
    pubdate = fields.Field(type=datetime, default=datetime.fromtimestamp(0))
    """The episode's publication date as an instance of
    :class:`datetime.datetime`."""

    author = fields.String()
    """The episode author's name."""

    block = fields.Field(type=bool, default=False)
    """Prevent an episode from appearing in the directory."""

    image = fields.Field(type=Image)
    """An image to be displayed with the episode as an instance of
    :class:`mopidy.models.Image`.

    """

    duration = fields.Field(type=timedelta)
    """The episode's duration as a :class:`datetime.timedelta`."""

    explicit = fields.Field(type=bool)
    """Indicates whether the episode contains explicit material."""

    order = fields.Integer()
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

    pubdate = fields.Field(type=datetime)
    """The podcast's publication date as an instance of
    :class:`datetime.datetime`."""

    author = fields.String()
    """The podcast author's name."""

    block = fields.Field(type=bool, default=False)
    """Prevent a podcast from appearing in the directory."""

    category = fields.String()
    """The main category of the podcast."""

    image = fields.Field(type=Image)
    """An image to be displayed with the podcast as an instance of
    :class:`mopidy.models.Image`.

    """

    explicit = fields.Field(type=bool)
    """Indicates whether the podcast contains explicit material."""

    complete = fields.Field(type=bool, default=False)
    """Indicates completion of the podcast."""

    newfeedurl = fields.URI()
    """Used to inform of new feed URL location."""

    description = fields.String()
    """A description of the podcast."""

    episodes = fields.Collection(type=Episode, container=tuple)
    """The podcast's episodes as a :class:`tuple` of :class:`Episode`
    instances.

    """
