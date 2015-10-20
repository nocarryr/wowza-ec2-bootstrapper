import os
import shutil
import datetime

import boto3

def get_is_vpc(inst_id, ec2=None):
    if ec2 is None:
        ec2 = boto3.client('ec2')
    data = ec2.describe_instances(InstanceIds=[inst_id])
    vpc_id = data.get('VpcId')
    return vpc_id is not None

# From http://www.wowza.com/forums/content.php?606-How-to-run-Wowza-Streaming-Engine-as-a-Named-User-(Linux-and-OS-X)
def configure_named_user_mode(config, **kwargs):
    if config.wowza.get('named_user_mode_configured'):
        return
    user = kwargs.get('user')
    group = kwargs.get('group')
    proc_conf = config.wowza.get('process_config')
    if proc_conf is None:
        proc_conf = config.wowza.add_config('process_config')
        proc_conf.update(dict(user=user, group=group))
    else:
        if user is None:
            user = proc_conf.get('user')
        elif user != proc_conf.get('user'):
            proc_conf.user = user
        if group is None:
            group = proc_conf.get('group')
        elif group != proc_conf.get('group'):
            proc_conf.group = group
    proc_conf.run_path = '/tmp'
    wowza_root = config.wowza.root_path
    
    class ScriptFile(object):
        def __init__(self, filename):
            self.filename = filename
            self._lines = None
        @property
        def lines(self):
            l = self._lines
            if l is None:
                l = self._lines = self.get_lines()
            return l
        def get_lines(self):
            s = self.read()
            return s.splitlines()
        def search_lines(self, search_str, start_line=0):
            i = start_line
            lines = self.lines[:]
            while True:
                try:
                    line = lines[i]
                except IndexError:
                    break
                if search_str in line:
                    yield i, line
                i += 1
        def make_backup(self):
            p, filename = os.path.split(self.filename)
            now = datetime.datetime.now()
            dt_str = now.strftime('%Y%m%d_%H%M%S-%f')
            backup_fn = '.'.join([filename, dt_str])
            shutil.copy2(os.path.join(p, filename), os.path.join(p, backup_fn))
        def read(self):
            with open(self.filename, 'r') as f:
                s = f.read()
            return s
        def write(self):
            self.make_backup()
            s = '\n'.join(self.lines)
            with open(self.filename, 'w') as f:
                f.write(s)
        
    # modify startup.sh
    f = ScriptFile(os.path.join(wowza_root, 'bin', 'startup.sh'))
    for i, line in f.search_lines('# check for root access'):
        for _i, _line in f.search_lines('', i+1):
            if _line.startswith('#'):
                break
            _line = '#%s' % (_line)
            f.lines[_i] = _line
            if line.startswith('fi'):
                break
        break
    f.write()
    
    # modify init scripts
    script_files = [
        'bin/WowzaStreamingEngine',
        'bin/wms.sh',
        'bin/shutdown.sh',
        'manager/bin/WowzaStreamingEngineManager',
        'manager/bin/startmgr.sh',
        'manager/bin/shutdownmgr.sh',
    ]
    for script_fn in script_files:
        f = ScriptFile(os.path.join(wowza_root, script_fn))
        for search_str in ['PID_FILE=', 'LOCK_FILE=']:
            for i, line in f.search_lines(search_str):
                conf_var, fn = line.split('=')
                fn = fn.strip('"')
                fn = os.path.join(proc_conf.run_path, os.path.basename(fn))
                line = '%s="%s"' % (conf_var, fn)
                f.lines[i] = line
                break
        f.write()
    
    ## TODO: chown?
    
    config.wowza.named_user_mode_configured = True
