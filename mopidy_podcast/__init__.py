from __future__ import unicode_literals

import os

from mopidy import config, ext, httpclient

__version__ = '2.0.0'


class Extension(ext.Extension):

    dist_name = 'Mopidy-Podcast'
    ext_name = 'podcast'
    version = __version__

    def get_default_config(self):
        return config.read(os.path.join(os.path.dirname(__file__), 'ext.conf'))

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['feeds'] = config.List(optional=True)
        schema['import_dir'] = config.Path(optional=True)
        schema['update_interval'] = config.Integer(minimum=3600)
        schema['browse_order'] = config.String(choices=['asc', 'desc'])
        schema['lookup_order'] = config.String(choices=['asc', 'desc'])
        schema['search_limit'] = config.Integer(optional=True, minimum=1)
        schema['cache_size'] = config.Integer(minimum=1)
        schema['cache_ttl'] = config.Integer(minimum=1)
        schema['timeout'] = config.Integer(optional=True, minimum=1)
        # no longer used
        schema['browse_limit'] = config.Deprecated()
        schema['search_details'] = config.Deprecated()
        schema['feeds_root_name'] = config.Deprecated()
        schema['feeds_cache_size'] = config.Deprecated()
        schema['feeds_cache_ttl'] = config.Deprecated()
        schema['feeds_timeout'] = config.Deprecated()
        return schema

    def setup(self, registry):
        from .backend import PodcastBackend
        registry.add('backend', PodcastBackend)

    @classmethod
    def get_url_opener(cls, config):
        import urllib2
        proxy = httpclient.format_proxy(config['proxy'])
        if proxy:
            opener = urllib2.build_opener(
                urllib2.ProxyHandler({'http': proxy, 'https': proxy})
            )
        else:
            opener = urllib2.build_opener()
        name = '%s/%s' % (cls.dist_name, cls.version)
        opener.addheaders = [
            ('User-agent', httpclient.format_user_agent(name))
        ]
        return opener
