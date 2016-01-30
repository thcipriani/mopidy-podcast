from __future__ import unicode_literals

from mopidy_podcast import Extension


def test_get_default_config():
    config = Extension().get_default_config()
    assert '[' + Extension.ext_name + ']' in config
    assert 'enabled = true' in config


def test_get_config_schema():
    schema = Extension().get_config_schema()
    assert 'lookup_order' in schema
    assert 'feeds' in schema
    assert 'update_interval' in schema
    assert 'cache_size' in schema
    assert 'cache_ttl' in schema
    assert 'timeout' in schema
