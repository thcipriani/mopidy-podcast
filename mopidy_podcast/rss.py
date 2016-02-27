from __future__ import unicode_literals

import datetime
import email.utils
import re
import xml.etree.ElementTree

from .models import Enclosure, Episode, Image, Podcast

_DURATION_RE = re.compile(r"""
(?:
    (?:(?P<hours>\d+):)?
    (?P<minutes>\d+):
)?
(?P<seconds>\d+)
""", flags=re.VERBOSE)

_NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'
}


def _int(e):
    return int(e.text) if e.text else None


def _bool(e):
    return e.text.strip().lower() == 'yes'


def _explicit(e):
    value = e.text.strip().lower()
    if value in ('yes', 'explicit', 'true'):
        return True
    elif value in ('clean', 'no', 'false'):
        return False
    else:
        return None


def _datetime(e):
    try:
        timestamp = email.utils.mktime_tz(email.utils.parsedate_tz(e.text))
    except AttributeError:
        return None
    except TypeError:
        return None
    else:
        return datetime.datetime.utcfromtimestamp(timestamp)


def _timedelta(e):
    try:
        groups = _DURATION_RE.match(e.text).groupdict('0')
    except AttributeError:
        return None
    except TypeError:
        return None
    else:
        return datetime.timedelta(**{k: int(v) for k, v in groups.items()})


def _category(e):
    return e.get('text').strip()


def _tag(etree, tag, convert=None, namespaces=_NAMESPACES):
    e = etree.find(tag, namespaces=namespaces)
    if e is None:
        return None
    elif convert:
        return convert(e)
    elif e.text:
        return e.text.strip()
    else:
        return None


def _image(e):
    kwargs = {}
    # handle both RSS and itunes images
    kwargs['uri'] = e.get('href', _tag(e, 'url'))
    for name in ('width', 'height'):
        kwargs[name] = _tag(e, name, _int)
    return Image(**kwargs)


def _enclosure(e):
    return Enclosure(
        uri=e.get('url'),
        type=e.get('type'),
        length=(int(e.get('length')) if e.get('length') else None)
    )


def _episode(e):
    kwargs = {
        'guid': _tag(e, 'guid'),
        'title': _tag(e, 'title'),
        'pubdate': _tag(e, 'pubDate', _datetime),
        'author': _tag(e, 'itunes:author'),
        'block': _tag(e, 'itunes:block', _bool),
        'image': _tag(e, 'itunes:image', _image),
        'duration': _tag(e, 'itunes:duration', _timedelta),
        'explicit': _tag(e, 'itunes:explicit', _explicit),
        'order': _tag(e, 'itunes:order', _int),
        'description': _tag(e, 'itunes:summary'),
        'enclosure': _tag(e, 'enclosure', _enclosure)
    }
    if not kwargs['guid']:
        kwargs['guid'] = kwargs['enclosure'].uri
    if not kwargs['description']:
        kwargs['description'] = _tag(e, 'description')
    return Episode(**kwargs)


def _podcast(e, uri, mtime=None):
    kwargs = {
        'uri': uri,
        'title': _tag(e, 'title'),
        'link': _tag(e, 'link'),
        'copyright': _tag(e, 'copyright'),
        'language': _tag(e, 'language'),
        'author': _tag(e, 'author'),
        'block': _tag(e, 'itunes:block', _bool),
        'category': _tag(e, 'itunes:category', _category),
        'image': _tag(e, 'itunes:image', _image),
        'explicit': _tag(e, 'itunes:explicit', _explicit),
        'complete': _tag(e, 'itunes:complete', _bool),
        'newfeedurl': _tag(e, 'itunes:new-feed-url'),
        'description': _tag(e, 'itunes:summary'),
        'episodes': tuple(map(_episode, e.iter(tag='item')))
    }
    # channel <pubDate> and <lastbuildDate> seems to be largely
    # unsupported or unreliable with podcasts
    if mtime:
        kwargs['pubdate'] = datetime.datetime.utcfromtimestamp(mtime)
    else:
        kwargs['pubdate'] = max(e.pubdate for e in kwargs['episodes'])
    if not kwargs['image']:
        kwargs['image'] = _tag(e, 'image', _image)
    if not kwargs['description']:
        kwargs['description'] = _tag(e, 'description')
    return Podcast(**kwargs)


def parse(source, uri=None):
    channel = xml.etree.ElementTree.parse(source).find('channel')
    if channel is None:
        raise TypeError('Not an RSS feed')
    header = getattr(source, 'headers', {}).get('last-modified')
    if header:
        mtime = email.utils.mktime_tz(email.utils.parsedate_tz(header))
    else:
        mtime = None
    return _podcast(channel, uri or source.geturl(), mtime)


if __name__ == '__main__':
    import argparse
    import contextlib
    import json
    import sys

    from urllib2 import urlopen

    import mopidy.models

    class JSONEncoder(mopidy.models.ModelJSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, datetime.timedelta):
                return obj.total_seconds()
            else:
                return super(JSONEncoder, self).default(obj)

    parser = argparse.ArgumentParser()
    parser.add_argument('uri', metavar='URI')
    parser.add_argument('-i', '--indent', type=int)
    parser.add_argument('-t', '--timeout', type=float)
    args = parser.parse_args()

    with contextlib.closing(urlopen(args.uri, timeout=args.timeout)) as source:
        obj = parse(source)
    json.dump(obj, sys.stdout, cls=JSONEncoder, indent=args.indent)
    sys.stdout.write('\n')
