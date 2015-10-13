import os
import json
import base64

import boto3
import requests
from requests.exceptions import RequestException
from requests.packages.urllib3.exceptions import HTTPError

CONF_FILENAME = os.path.expanduser('~/.wowza_ec2_conf.json')

class Config(object):
    _base_config_tree = dict(
        instance_metadata={}, 
        instance_tags={}, 
        wowza={
            'root_path':'/usr/local/WowzaStreamingEngine', 
            'log_path':'/usr/local/WowzaStreamingEngine/logs', 
        }, 
        action_data={}, 
    )
    def __init__(self, initdict=None, **kwargs):
        self._conf_filename = kwargs.get('_conf_filename', CONF_FILENAME)
        self._data = {}
        if initdict is None:
            initdict = {}
        kwargs.update(initdict)
        for key, val in kwargs.items():
            self[key] = val
    def _init_base_config_tree(self):
        for key, val in self._base_config_tree.items():
            self.add_config(key, val.copy())
    def __setitem__(self, key, item):
        if key == '_conf_filename':
            self._conf_filename = item
            return
        self._data[key] = item
    def __getitem__(self, key):
        return self._data[key]
    def __getattr__(self, attr):
        if hasattr(self, '_data') and attr in self._data:
            return self._data[attr]
        raise AttributeError('%r object has no attribute %r' %
                             (self.__class__, attr))
    def __setattr__(self, attr, item):
        if attr in ['_conf_filename', '_data']:
            super(Config, self).__setattr__(attr, item)
        else:
            self._data[attr] = item
    def __len__(self):
        return self._data.__len__()
    def __iter__(self):
        return self._data.__iter__()
    def __contains__(self, item):
        return self._data.__contains__(item)
    def keys(self):
        return self._data.keys()
    def values(self):
        return self._data.values()
    def items(self):
        return self._data.items()
    def get(self, key, default=None):
        return self._data.get(key, default)
    def update(self, other):
        if isinstance(other, Config):
            self._data.update(other._data)
        else:
            for key, item in other.items():
                if key in self and isinstance(self[key], Config):
                    self[key].update(item)
                else:
                    self[key] = item
    def setdefault(self, key, default):
        self._data.setdefault(key, default)
    def add_config(self, key, initdict=None, **kwargs):
        if key in self:
            c = self[key]
            if initdict is not None:
                c.update(initdict)
            if not isinstance(c, Config):
                c = Config(c, **kwargs)
                self[key] = c
            else:
                c.update(kwargs)
            return c
        c = Config(initdict, **kwargs)
        self[key] = c
        return c
    def to_json(self, filename=None, **kwargs):
        d = self._serialize()
        s = json.dumps(d, **kwargs)
        if filename is None:
            filename = self._conf_filename
        if filename is None:
            return
        with open(filename, 'w') as f:
            f.write(s)
        return s
    @classmethod
    def from_json(cls, **kwargs):
        s = kwargs.get('json')
        fn = kwargs.get('filename')
        if fn is None:
            fn = kwargs.get('_conf_filename')
        url = kwargs.get('url')
        data = None
        if s is None:
            if fn is not None:
                with open(fn, 'r') as f:
                    s = f.read()
            elif url is not None:
                r = requests.get(url)
                data = r.json()
        if data is None:
            if s is None:
                data = {}
            else:
                data = json.loads(s)
        return cls._deserialize(data, _conf_filename=fn)
    def _serialize(self):
        d = {'__class__':'Config'}
        for key, val in self.items():
            if isinstance(val, Config):
                val = val._serialize()
            d[key] = val
        return d
    @classmethod
    def _deserialize(cls, data, **kwargs):
        if '__class__' in data:
            del data['__class__']
        conf_dict = {}
        for key, val in data.copy().items():
            if isinstance(val, dict) and val.get('__class__') == 'Config':
                conf_dict[key] = val
                del data[key]
        obj = cls(data, **kwargs)
        for key, val in conf_dict.items():
            obj[key] = cls._deserialize(val)
        return obj
    def __repr__(self):
        return repr(self._data)
    def __str__(self):
        return str(self._data)

def build_config(build_default=True, **kwargs):
    if build_default:
        kwargs.setdefault('_conf_filename', CONF_FILENAME)
    _config = Config.from_json(**kwargs)
    conf_keys = set(Config._base_config_tree.keys())
    if conf_keys & set(_config.keys()) != conf_keys:
        _config._init_base_config_tree()
    return _config

config = build_config()

def get_metadata(_config=None):
    if _config is None:
        _config = config
    base_url = 'http://169.254.169.254/latest/meta-data'
    def get_item(uri):
        uri = '/'.join([base_url, uri])
        r = requests.get(uri)
        assert r.status_code == 200
        return r.content
    root_categories = ['ami-id', 'instance-id', 'instance-type', 
        'public-hostname', 'public-ipv4']
    categories = {'_'.join(c.split('-')):c for c in root_categories}
    categories['availability_zone'] = 'placement/availability-zone'
    mdata = _config.add_config('instance_metadata')
    for key, uri in categories.items():
        mdata[key] = get_item(uri)
    mdata['region'] = mdata['availability_zone'][:-1]
    
def get_userdata(_config=None):
    if _config is None:
        _config = config
    if not _config.is_ec2_instance:
        _config.instance_userdata = None
        return
    ec2 = boto3.resource('ec2')
    instobj = ec2.Instance(_config.instance_metadata.instance_id)
    r = instobj.describe_attribute(Attribute='userData')
    udata = r.get('UserData', {}).get('Value')
    if udata is not None:
        udata = base64.b64decode(udata)
        try:
            d = json.loads(udata)
        except ValueError:
            d = None
        if d is not None:
            udata = d
    if isinstance(udata, dict):
        _config.add_config('instance_userdata', udata)
    else:
        _config.instance_userdata = udata
    
def get_tags(_config=None):
    if _config is None:
        _config = config
    if not _config.is_ec2_instance:
        _config.instance_tags = {}
        return
    ec2 = boto3.resource('ec2')
    instobj = ec2.Instance(_config.instance_metadata.instance_id)
    tags = {}
    for tag in instobj.tags:
        tags[tag['Key']] = tag['Value']
    _config.add_config('instance_tags', tags)

def get_web_conf(_config=None):
    if _config is None:
        _config = config
    conf_url = None
    udata = _config.instance_userdata
    if isinstance(udata, dict):
        conf_url = udata.get('conf_url')
    if conf_url is None:
        conf_url = _config.instance_tags.get('conf_url')
    if conf_url is None:
        return
    if '?' not in conf_url:
        conf_url = '?'.join([conf_url, _config.instance_metadata.instance_id])
    r = requests.get(conf_url)
    if r.status_code != 200:
        return
    data = r.json()
    _config.update(data)

def set_config_defaults(_config=None):
    if _config is None:
        _config = config
    if not os.path.exists(CONF_FILENAME):
        try:
            get_metadata(_config)
        except RequestException:
            _config.is_ec2_instance = False
        except HTTPError:
            _config.is_ec2_instance = False
        except AssertionError:
            _config.is_ec2_instance = False
        else:
            _config.is_ec2_instance = True

        from wowza_ec2_bootstrapper import awsconfig
        awsconfig.build_config_file(_config)

        get_userdata(_config)
        get_tags(_config)
        get_web_conf(_config)
        
        _config.to_json(indent=2)

set_config_defaults()
