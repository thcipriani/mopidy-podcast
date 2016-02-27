from __future__ import unicode_literals

import datetime
import logging
import os
import sqlite3

from . import Extension

DEFAULT_PARAMS = {
    'episode_title': None,
    'podcast_title': None,
    'episode_author': None,
    'podcast_author': None,
    'category': None,
    'pubdate': None,
    'description': None,
    'any': None,
    'uri': None,
    'limit': -1,
    'offset': 0
}

FTPODCAST_COLS = {
    'any': 'ftpodcast',
    'category': 'category',
    'podcast_author': 'author',
    'podcast_title': 'title'
}

FTEPISODE_COLS = {
    'any': 'ftepisode',
    'category': 'category',
    'description': 'description',
    'episode_author': 'episode_author',
    'episode_title': 'episode_title',
    'podcast_author': 'podcast_author',
    'podcast_title': 'podcast_title',
    'pubdate': 'pubdate'
}

DISTINCT_QUERY = """
SELECT DISTINCT %s AS field
  FROM episode JOIN podcast USING (uri)
 WHERE field IS NOT NULL
   AND (:any IS NULL OR :any IN
        (episode.title, episode.author, episode.description,
         podcast.title, podcast.author, podcast.category)
       )
   AND (:podcast_title IS NULL OR :podcast_title = podcast.title)
   AND (:episode_title IS NULL OR :episode_title = episode.title)
   AND (:podcast_author IS NULL OR :podcast_author = podcast.author)
   AND (:episode_author IS NULL OR :episode_author = episode.author)
   AND (:category IS NULL OR :category = category)
   AND (:pubdate IS NULL OR date(pubdate) = :pubdate)
   AND (:description IS NULL OR :description = episode.description)
"""

FULLTEXT_QUERY = """
SELECT uri AS uri, title AS title, NULL AS guid, datetime('now') AS rank
  FROM podcast
 WHERE rowid in (%s)
   AND :uri IS NULL
 UNION
SELECT uri AS uri, title AS title, guid AS guid, pubdate as rank
  FROM episode
 WHERE rowid in (%s)
   AND (:uri IS NULL OR :uri = uri)
 ORDER BY rank DESC, title COLLATE NOCASE
 LIMIT :limit OFFSET :offset
"""

INDEXED_QUERY = """
SELECT uri AS uri, title AS title, NULL AS guid, datetime('now') AS rank
  FROM podcast
 WHERE (:any IS NULL OR :any IN (title, author, category))
   AND (:podcast_title IS NULL OR :podcast_title = title)
   AND :episode_title IS NULL
   AND (:podcast_author IS NULL OR :podcast_author = author)
   AND :episode_author IS NULL
   AND (:category IS NULL OR :category = category)
   AND :pubdate IS NULL
   AND :description IS NULL
   AND :uri IS NULL
 UNION
SELECT uri AS uri, episode.title AS title, guid AS guid, pubdate AS rank
  FROM episode JOIN podcast USING (uri)
 WHERE (:any IS NULL OR :any IN
        (episode.title, episode.author, episode.description,
         podcast.title, podcast.author, podcast.category)
       )
   AND (:podcast_title IS NULL OR :podcast_title = podcast.title)
   AND (:episode_title IS NULL OR :episode_title = episode.title)
   AND (:podcast_author IS NULL OR :podcast_author = podcast.author)
   AND (:episode_author IS NULL OR :episode_author = episode.author)
   AND (:category IS NULL OR :category = category)
   AND (:pubdate IS NULL OR pubdate LIKE date(:pubdate) || '%')
   AND (:description IS NULL OR :description = episode.description)
   AND (:uri IS NULL OR :uri = uri)
 ORDER BY rank DESC, title COLLATE NOCASE
 LIMIT :limit OFFSET :offset
"""

LIST_PODCASTS_QUERY = """
SELECT uri AS uri, title AS title
  FROM podcast
 ORDER BY title COLLATE NOCASE
"""

LIST_EPISODES_QUERY = """
SELECT guid AS guid, title AS title
  FROM episode
 WHERE uri = :uri
 ORDER BY title COLLATE NOCASE
"""

PUBDATE_QUERY = """
SELECT pubdate FROM podcast WHERE uri = :uri
"""

UPDATE_PODCAST = """
INSERT OR REPLACE INTO podcast (
    uri, title, link, copyright, language, pubdate, author, block,
    category, explicit, complete, newfeedurl, description
) VALUES (
    :uri, :title, :link, :copyright, :language, :pubdate, :author, :block,
    :category, :explicit, :complete, :newfeedurl, :description
)
"""

UPDATE_EPISODE = """
INSERT OR REPLACE INTO episode (
    uri, guid, title, pubdate, author, block, duration, explicit,
    description
) VALUES (
    :uri, :guid, :title, :pubdate, :author, :block, :duration, :explicit,
    :description
)
"""

DELETE_PODCAST = """
DELETE FROM podcast WHERE uri = :uri
"""

logger = logging.getLogger(__name__)

schema_version = 1

# store datetime.timedelta as SQLite REAL type
sqlite3.register_adapter(datetime.timedelta, datetime.timedelta.total_seconds)


class Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        sqlite3.Connection.__init__(self, *args, **kwargs)
        self.execute('PRAGMA foreign_keys = ON')
        self.execute('PRAGMA recursive_triggers = ON')
        self.row_factory = sqlite3.Row


def connect(path, **kwargs):
    return sqlite3.connect(path, factory=Connection, **kwargs)


def init(cursor, scripts=os.path.join(os.path.dirname(__file__), 'sql')):
    user_version, = cursor.execute('PRAGMA user_version').fetchone()
    while user_version != schema_version:
        if user_version:
            message = 'Upgrading %%s database schema v%d' % user_version
            filename = 'upgrade-v%d.sql' % user_version
        else:
            message = 'Creating %%s database schema v%d' % schema_version
            filename = 'schema.sql'
        logger.info(message, Extension.dist_name)
        with open(os.path.join(scripts, filename)) as f:
            cursor.executescript(f.read())
        version, = cursor.execute('PRAGMA user_version').fetchone()
        assert version != user_version
        user_version = version
    logger.debug('Using database schema v%s', user_version)
    return user_version


def list(connection, uri=None):
    if uri is None:
        return connection.execute(LIST_PODCASTS_QUERY)
    else:
        return connection.execute(LIST_EPISODES_QUERY, {uri: uri})


def pubdate(connection, uri):
    col, = connection.execute(PUBDATE_QUERY, {'uri': uri}).fetchone() or [None]
    if col:
        return datetime.datetime.strptime(col, '%Y-%m-%d %H:%M:%S')
    else:
        return None


def distinct(connection, expr, **params):
    sql = DISTINCT_QUERY % expr
    params = dict(DEFAULT_PARAMS, **params)
    logger.debug('Distinct query: %s %r', sql, params)
    return connection.execute(sql, params)


def search(connection, **params):
    params = dict(DEFAULT_PARAMS, **params)
    logger.debug('Indexed query: %s %r', INDEXED_QUERY, params)
    return connection.execute(INDEXED_QUERY, params)


def ftsearch(connection, uri=None, offset=0, limit=-1, **params):
    # SQLite MATCH clauses cannot be combined with AND or OR, and
    # phrase queries may not be used with column names...
    sql = FULLTEXT_QUERY % (
        ' INTERSECT '.join(
            _match('ftpodcast', FTPODCAST_COLS, key) for key in params
        ),
        ' INTERSECT '.join(
            _match('ftepisode', FTEPISODE_COLS, key) for key in params
        )
    )
    params.update(limit=limit, offset=offset, uri=uri)
    logger.debug('Fulltext query: %s %r', sql, params)
    return connection.execute(sql, params)


def update(connection, podcast):
    if podcast.pubdate and podcast.pubdate == pubdate(connection, podcast.uri):
        return  # assume nothing changed
    connection.execute(UPDATE_PODCAST, {
        'uri': podcast.uri,
        'title': podcast.title,
        'link': podcast.link,
        'copyright': podcast.copyright,
        'language': podcast.language,
        'pubdate': podcast.pubdate,
        'author': podcast.author,
        'block': podcast.block,
        'category': podcast.category,
        'explicit': podcast.explicit,
        'complete': podcast.complete,
        'newfeedurl': podcast.newfeedurl,
        'description': podcast.description
    })
    connection.executemany(UPDATE_EPISODE, [{
        'uri': podcast.uri,
        'guid': episode.guid,
        'title': episode.title,
        'pubdate': episode.pubdate,
        'author': episode.author,
        'block': episode.block,
        'duration': episode.duration,
        'explicit': episode.explicit,
        'description': episode.description
    } for episode in podcast.episodes])


def delete(connection, uri):
    return connection.execute(DELETE_PODCAST, {'uri': uri})


def _match(table, cols, key):
    try:
        col = cols[key]
    except KeyError:
        return 'SELECT NULL'
    else:
        return 'SELECT docid FROM %s WHERE %s MATCH :%s' % (table, col, key)
