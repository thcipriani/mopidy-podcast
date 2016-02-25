from __future__ import unicode_literals

import datetime
import logging
import os
import re
import sqlite3

from . import Extension, models

PARAMETERS = {
   None: 'any',
   models.Episode.author: 'episode_author',
   models.Episode.description: 'description',
   models.Episode.pubdate: 'pubdate',
   models.Episode.title: 'episode_title',
   models.Podcast.author: 'podcast_author',
   models.Podcast.category: 'category',
   models.Podcast.title: 'podcast_title'
}

FTPODCAST_COLS = {
    'any': 'ftpodcast',
    'podcast_title': 'title',
    'podcast_author': 'author',
    'category': 'category',
    'description': 'description'
}

FTEPISODE_COLS = {
    'any': 'ftepisode',
    'podcast_title': 'podcast_title',
    'podcast_author': 'podcast_author',
    'episode_title': 'episode_title',
    'episode_author': 'episode_author',
    'pubdate': 'pubdate',
    'category': 'category',
    'description': 'description'
}

FULLTEXT_QUERY = """
    SELECT uri AS uri, title AS title, NULL AS guid
      FROM podcast
     WHERE rowid in (%s)
     UNION
    SELECT uri AS uri, title AS title, guid AS guid
      FROM episode
     WHERE rowid in (%s)
     ORDER BY title, uri, guid
     LIMIT :limit OFFSET :offset
"""

INDEXED_QUERY = """
    SELECT uri AS uri, title AS title, NULL AS guid
      FROM podcast
     WHERE (:any IS NULL OR :any IN (title, author, category, description))
       AND (:podcast_title IS NULL OR :podcast_title = title)
       AND (:episode_title IS NULL)
       AND (:podcast_author IS NULL OR :podcast_author = author)
       AND (:episode_author IS NULL)
       AND (:category IS NULL OR :category = category)
       AND (:pubdate IS NULL)
       AND (:description IS NULL OR :description = description)
     UNION
    SELECT e.uri AS uri, e.title AS title, e.guid AS guid
      FROM episode AS e
      JOIN podcast AS p USING (uri)
     WHERE (:any IS NULL OR :any IN (e.title, e.author, e.description))
       AND (:podcast_title IS NULL OR :podcast_title = p.title)
       AND (:episode_title IS NULL OR :episode_title = e.title)
       AND (:podcast_author IS NULL OR :podcast_author = p.author)
       AND (:episode_author IS NULL OR :episode_author = e.author)
       AND (:category IS NULL OR :category = p.category)
       AND (:pubdate IS NULL OR e.pubdate LIKE date(:pubdate) || '%')
       AND (:description IS NULL OR :description = e.description)
     ORDER BY title, uri, guid
     LIMIT :limit OFFSET :offset
"""

LIST_QUERY = """
    SELECT uri AS uri, title AS title
      FROM podcast
     ORDER BY title, uri
"""

UPDATE_PODCAST = """
    INSERT OR REPLACE INTO podcast (
        uri,
        title,
        link,
        copyright,
        language,
        author,
        block,
        category,
        explicit,
        complete,
        newfeedurl,
        description
    ) VALUES (
        :uri,
        :title,
        :link,
        :copyright,
        :language,
        :author,
        :block,
        :category,
        :explicit,
        :complete,
        :newfeedurl,
        :description
    )
"""

UPDATE_EPISODE = """
    INSERT OR REPLACE INTO episode (
        uri,
        guid,
        title,
        pubdate,
        author,
        block,
        duration,
        explicit,
        description
    ) VALUES (
        :uri,
        :guid,
        :title,
        :pubdate,
        :author,
        :block,
        :duration,
        :explicit,
        :description
    )
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


def list(cursor):
    return cursor.execute(LIST_QUERY)


def search(cursor, query, offset=0, limit=None):
    if limit is None:
        limit = -1
    if query.exact:
        return _indexed_search(cursor, query, offset, limit)
    else:
        return _fulltext_search(cursor, query, offset, limit)


def update(cursor, podcast):
    cursor.execute(UPDATE_PODCAST, {
        'uri': podcast.uri,
        'title': podcast.title,
        'link': podcast.link,
        'copyright': podcast.copyright,
        'language': podcast.language,
        'author': podcast.author,
        'block': podcast.block,
        'category': podcast.category,
        'explicit': podcast.explicit,
        'complete': podcast.complete,
        'newfeedurl': podcast.newfeedurl,
        'description': podcast.description
    })
    cursor.executemany(UPDATE_EPISODE, [{
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


def cleanup(cursor, uris):
    sql = 'DELETE FROM podcast WHERE uri NOT IN (%s)' % (
        ', '.join(['?'] * len(uris))
    )
    return cursor.execute(sql, uris)


def _indexed_search(cursor, query, offset=0, limit=-1):
    params = dict.fromkeys(PARAMETERS.values(), None)
    for term in query.terms:
        params[PARAMETERS[term.field]] = ' '.join(term.values)
    params.update(offset=offset, limit=limit)
    return cursor.execute(INDEXED_QUERY, params)


def _fulltext_search(cursor, query, offset=0, limit=-1):
    params = dict.fromkeys(PARAMETERS.values(), None)
    for term in query.terms:
        params[PARAMETERS[term.field]] = ' '.join(map(_quote, term.values))
    params.update(offset=offset, limit=limit)
    # SQLite MATCH clauses cannot be combined with AND or OR
    # TODO: skip podcast search if field not available?
    sql = FULLTEXT_QUERY % (
        ' INTERSECT '.join(
            'SELECT docid FROM ftpodcast WHERE %s MATCH :%s' % (col, key)
            for key, col in FTPODCAST_COLS.items()
            if params[key] is not None
        ),
        ' INTERSECT '.join(
            'SELECT docid FROM ftepisode WHERE %s MATCH :%s' % (col, key)
            for key, col in FTEPISODE_COLS.items()
            if params[key] is not None
        )
    )
    # logger.debug('Fulltext query: %r %r', sql, params)
    return cursor.execute(sql, params)


def _quote(value, re=re.compile(r'["^*]|NEAR|AND|OR')):
    return '"%s"' % re.sub('', value)
