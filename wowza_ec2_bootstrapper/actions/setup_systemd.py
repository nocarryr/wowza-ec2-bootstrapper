import os
import pwd
import grp

from wowza_ec2_bootstrapper.actions import BaseAction
from wowza_ec2_bootstrapper.utils import configure_named_user_mode

ENGINE_UNIT_TEMPLATE = '''
[Unit]
Description=WowzaStreamingEngine
After=syslog.target
After=network.target
After=local-fs.target
After=remote-fs.target

[Service]
Type=simple
User=%(user)s
Group=%(group)s
ExecStart=%(wowza_root)s/bin/WowzaStreamingEngine start
ExecStop=%(wowza_root)s/bin/WowzaStreamingEngine start
RemainAfterExit=yes

# Give a reasonable amount of time for the server to start up/shut down
TimeoutSec=300

[Install]
WantedBy=multi-user.target
'''

MANAGER_UNIT_TEMPLATE = '''
[Unit]
Description=WowzaStreamingEngineManager
After=syslog.target
After=network.target
After=local-fs.target
After=remote-fs.target

[Service]
Type=simple
User=%(user)s
Group=%(group)s
ExecStart=%(wowza_root)s/manager/bin/WowzaStreamingEngineManager start
ExecStop=%(wowza_root)s/manager/bin/WowzaStreamingEngineManager start
RemainAfterExit=yes

# Give a reasonable amount of time for the server to start up/shut down
TimeoutSec=300

[Install]
WantedBy=multi-user.target
'''

class SystemdServiceConf(BaseAction):
    action_fields = dict(
        user={'default':'root'}, 
        group={'default':'root'}, 
        unit_type={'default':'system', 'options':['system', 'user']}, 
    )
    def do_action(self, **kwargs):
        fields = self.action_fields
        template_data = {}
        for key in ['user', 'group']:
            template_data[key] = kwargs.get(key, fields[key]['default'])
        template_data['wowza_root'] = self.config.wowza.root_path
        unit_type = kwargs.get('unit_type', fields['unit_type']['default'])
        if unit_type == 'user':
            if template_data['user'] == 'root':
                pw_data = pwd.getpwuid(os.getuid())
                template_data['user'] = pw_data.pw_name
            else:
                pw_data = pwd.getpwnam(template_data['user'])
            if template_data['group'] == 'root':
                template_data['group'] = grp.getgrgid(pw_data.pw_gid).gr_name
            unit_file_path = os.path.join(pw_data.pw_dir, '.config/systemd/user')
            if not os.path.exists(unit_file_path):
                os.makedirs(unit_file_path)
            configure_named_user_mode(self.config, **template_data)
        else:
            unit_file_path = '/etc/systemd/system/'
        engine_unit = ENGINE_UNIT_TEMPLATE % template_data
        manager_unit = MANAGER_UNIT_TEMPLATE % template_data
        fn = os.path.join(unit_file_path, 'WowzaStreamingEngine')
        with open(fn, 'w') as f:
            f.write(engine_unit)
        fn = os.path.join(unit_file_path, 'WowzaStreamingEngineManager')
        with open(fn, 'w') as f:
            f.write(manager_unit)
        
        
        
