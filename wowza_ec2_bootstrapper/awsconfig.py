import os

    
def build_config_file(config):
    if not config.is_ec2_instance:
        return
    fn = os.path.expanduser('~/.aws/config')
    if os.path.exists(fn):
        return
    region = config.instance_metadata.region
    s = '\n'.join([
        '[default]', 
        'region=%s' % (region)
    ])
    if not os.path.exists(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn))
    with open(fn, 'w') as f:
        f.write(s)
    
    
