import json
import base64

import boto3
import requests
from requests.exceptions import RequestException
from requests.packages.urllib3.exceptions import HTTPError

class Config(object):
    def __init__(self, initdict=None, **kwargs):
        self._data = {}
        if initdict is None:
            initdict = {}
        kwargs.update(initdict)
        for key, val in kwargs.items():
            self[key] = val
    def __setitem__(self, key, item):
        self._data[key] = item
    def __getitem__(self, key):
        return self._data[key]
    def __getattr__(self, attr):
        if hasattr(self, '_data') and attr in self._data:
            return self._data[attr]
        raise AttributeError('%r object has no attribute %r' %
                             (self.__class__, attr))
    def __setattr__(self, attr, item):
        if attr == '_data':
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
            self._data.update(other)
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
    def __repr__(self):
        return repr(self._data)
    def __str__(self):
        return str(self._data)

config = Config()

def get_metadata():
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
    mdata = config.add_config('instance_metadata')
    for key, uri in categories.items():
        mdata[key] = get_item(uri)
    mdata['region'] = mdata['availability_zone'][:-1]
    
def get_userdata():
    if not config.is_ec2_instance:
        config.instance_userdata = None
        return
    ec2 = boto3.resource('ec2')
    instobj = ec2.Instance(config.instance_metadata.instance_id)
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
        config.add_config('instance_userdata', udata)
    else:
        config.instance_userdata = udata
    
def get_tags():
    if not config.is_ec2_instance:
        config.instance_tags = None
        return
    ec2 = boto3.resource('ec2')
    instobj = ec2.Instance(config.instance_metadata.instance_id)
    tags = {}
    for tag in instobj.tags:
        tags[tag.key] = tag.value
    config.add_config('instance_tags', tags)

try:
    get_metadata()
except RequestException:
    config.is_ec2_instance = False
except HTTPError:
    config.is_ec2_instance = False
else:
    config.is_ec2_instance = True

from wowza_ec2_bootstrapper import awsconfig
awsconfig.build_config_file()

get_userdata()
get_tags()
