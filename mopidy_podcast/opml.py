from __future__ import unicode_literals

import datetime
import email.utils
import logging
import xml.etree.ElementTree

from .models import Outline

CONVERTERS = {
    Outline.INCLUDE: lambda e: Outline.include(
        category=e.get('category'),
        created=_datetime(e.get('created')),
        text=e.get('text'),
        uri=e.get('url')
    ),
    Outline.LINK: lambda e: Outline.link(
        category=e.get('category'),
        created=_datetime(e.get('created')),
        text=e.get('text'),
        uri=e.get('url')
    ),
    Outline.RSS: lambda e: Outline.rss(
        category=e.get('category'),
        created=_datetime(e.get('created')),
        description=e.get('description'),
        language=e.get('language'),
        text=e.get('text'),
        title=e.get('title'),
        uri=e.get('xmlUrl'),
    ),
    '': lambda e: Outline(
        category=e.get('category'),
        created=_datetime(e.get('created')),
        text=e.get('text')
    )
}

logger = logging.getLogger(__name__)


def _datetime(s):
    try:
        timestamp = email.utils.mktime_tz(email.utils.parsedate_tz(s))
    except AttributeError:
        return None
    except TypeError:
        return None
    else:
        return datetime.datetime.utcfromtimestamp(timestamp)


def parse(source, uri=None):
    root = xml.etree.ElementTree.parse(source).getroot()
    if root.tag != 'opml' or root.find('body') is None:
        raise TypeError('Not a valid OPML document')
    result = []
    for e in root.find('body').iter(tag='outline'):
        type = e.get('type', '').lower()
        try:
            outline = CONVERTERS[type]
        except KeyError:
            logger.warning('Outline type "%s" not supported', type)
        else:
            result.append(outline(e))
    return result


if __name__ == '__main__':
    import argparse
    import contextlib
    import json
    import logging
    import urllib2
    import sys

    from .models import ModelJSONEncoder

    parser = argparse.ArgumentParser()
    parser.add_argument('uri', metavar='URI')
    parser.add_argument('-i', '--indent', type=int)
    parser.add_argument('-t', '--timeout', type=float)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARN)

    opener = urllib2.build_opener()  # TODO: proxies, auth, etc.

    with contextlib.closing(opener.open(args.uri, timeout=args.timeout)) as f:
        obj = parse(f)
    json.dump(obj, sys.stdout, cls=ModelJSONEncoder, indent=args.indent)
    sys.stdout.write('\n')
