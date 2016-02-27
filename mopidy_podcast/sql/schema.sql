-- Mopidy-Podcast schema

BEGIN EXCLUSIVE TRANSACTION;

PRAGMA user_version = 1;                -- schema version

CREATE TABLE podcast (
    uri             TEXT PRIMARY KEY,   -- podcast URI
    title           TEXT NOT NULL,      -- podcast title
    link            TEXT,               -- URL of the podcast's website
    copyright       TEXT,               -- podcast copyright notice
    language        TEXT,               -- ISO two-letter language code
    pubdate         TEXT,               -- podcast last publication date and time
    author          TEXT,               -- podcast author's name
    block           INTEGER,            -- whether the podcast should be blocked
    category        TEXT,               -- the podcast's main category
    explicit        INTEGER,            -- whether the podcast contains explicit material
    complete        INTEGER,            -- indicates completion of the podcast
    newfeedurl      TEXT,               -- new feed URL location
    description     TEXT                -- description of the podcast
);

CREATE TABLE episode (
    uri             TEXT REFERENCES podcast(uri) ON DELETE CASCADE ON UPDATE CASCADE,
    guid            TEXT NOT NULL,      -- episode GUID
    title           TEXT NOT NULL,      -- episode title
    pubdate         TEXT,               -- episode publication date and time
    author          TEXT,               -- episode author's name
    block           INTEGER,            -- whether the epidode should be blocked
    duration        REAL,               -- episode duration in seconds
    explicit        INTEGER,            -- whether the episode contains explicit material
    description     TEXT,               -- description of the episode
    PRIMARY KEY (uri, guid)             -- GUIDs may not be as unique as they shoulde be
);

CREATE INDEX podcast_title_index        ON podcast (title);
CREATE INDEX podcast_author_index       ON podcast (author);
CREATE INDEX podcast_category_index     ON podcast (category);
CREATE INDEX podcast_description_index  ON podcast (description);
CREATE INDEX podcast_block_index        ON podcast (block);
CREATE INDEX podcast_explicit_index     ON podcast (explicit);

CREATE INDEX episode_title_index        ON episode (title);
CREATE INDEX episode_author_index       ON episode (author);
CREATE INDEX episode_pubdate_index      ON episode (pubdate);
CREATE INDEX episode_description_index  ON episode (description);
CREATE INDEX episode_block_index        ON episode (block);
CREATE INDEX episode_explicit_index     ON episode (explicit);

-- Full-text search tables

CREATE VIRTUAL TABLE ftpodcast USING fts4 (
    title,
    author,
    category,
    description
);

CREATE VIRTUAL TABLE ftepisode USING fts4 (
    episode_title,
    episode_author,
    pubdate,
    description,
    podcast_title,
    podcast_author,
    category
);

-- Full-text search triggers for podcast

CREATE TRIGGER podcast_after_insert AFTER INSERT ON podcast
BEGIN
    INSERT INTO ftpodcast (docid, title, author, category, description)
    SELECT rowid, title, author, category, description
      FROM podcast
     WHERE rowid = new.rowid;
END;

CREATE TRIGGER podcast_after_update AFTER UPDATE ON podcast
BEGIN
    INSERT INTO ftpodcast (docid, title, author, category, description)
    SELECT rowid, title, author, category, description
      FROM podcast
     WHERE rowid = new.rowid;
END;

CREATE TRIGGER podcast_before_update BEFORE UPDATE ON podcast
BEGIN
    DELETE FROM ftpodcast WHERE docid = old.rowid;
END;

CREATE TRIGGER podcast_before_delete BEFORE DELETE ON podcast
BEGIN
    DELETE FROM ftpodcast WHERE docid = old.rowid;
END;

-- Full-text search triggers for episode

CREATE TRIGGER episode_after_insert AFTER INSERT ON episode
BEGIN
    INSERT INTO ftepisode (
           docid, episode_title, episode_author, pubdate, description,
           podcast_title, podcast_author, category
    )
    SELECT e.rowid, e.title, e.author, e.pubdate, e.description,
           p.title, p.author, p.category
      FROM episode AS e
      JOIN podcast AS p USING (uri)
     WHERE e.rowid = new.rowid;
END;

CREATE TRIGGER episode_after_update AFTER UPDATE ON episode
BEGIN
    INSERT INTO ftepisode (
           docid, episode_title, episode_author, pubdate, description,
           podcast_title, podcast_author, category
    )
    SELECT e.rowid, e.title, e.author, e.pubdate, e.description,
           p.title, p.author, p.category
      FROM episode AS e
      JOIN podcast AS p USING (uri)
     WHERE e.rowid = new.rowid;
END;

CREATE TRIGGER episode_before_update BEFORE UPDATE ON episode
BEGIN
    DELETE FROM ftepisode WHERE docid = old.rowid;
END;

CREATE TRIGGER episode_before_delete BEFORE DELETE ON episode
BEGIN
    DELETE FROM ftepisode WHERE docid = old.rowid;
END;

END TRANSACTION;
