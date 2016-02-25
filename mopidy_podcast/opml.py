from __future__ import unicode_literals

import xml.etree.ElementTree

# http://dev.opml.org/spec2.html

OUTLINES = {
    None: lambda e: {
        'type': e.get('type'),
        'text': e.get('text')
    },
    'include': lambda e: {
        'type': 'include',
        'text': e.get('text'),
        'url': e.get('url')
    },
    'link': lambda e: {
        'type': 'link',
        'text': e.get('text'),
        'url': e.get('url')
    },
    'rss': lambda e: {
        'type': 'rss',
        'text': e.get('text'),
        'xmlUrl': e.get('xmlUrl')
    },
    '': lambda e: {
        'text': e.get('text')
    }
}


def parse(source):
    root = xml.etree.ElementTree.parse(source).getroot()
    if root.tag != 'opml' or root.find('body') is None:
        raise TypeError('Not a valid OPML document')
    outlines = []
    for e in root.find('body').iter(tag='outline'):
        type = e.get('type', '').lower()
        try:
            outline = OUTLINES[type]
        except KeyError:
            outline = OUTLINES[None]
        outlines.append(outline(e))
    return outlines


if __name__ == '__main__':
    import argparse
    import contextlib
    import json
    import urllib2
    import urlparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument('uri', metavar='PATH | URI')
    parser.add_argument('-i', '--indent', type=int)
    parser.add_argument('-t', '--timeout', type=float)
    args = parser.parse_args()

    if urlparse.urlsplit(args.uri).scheme:
        fh = urllib2.urlopen(args.uri, timeout=args.timeout)
    else:
        fh = open(args.uri)
    with contextlib.closing(fh) as source:
        outlines = parse(source)
    json.dump(outlines, sys.stdout, indent=args.indent)
    sys.stdout.write('\n')
