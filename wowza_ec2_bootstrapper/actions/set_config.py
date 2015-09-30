import os

import requests

from wowza_ec2_bootstrapper.actions import BaseAction

class SetConfig(BaseAction):
    @property
    def conf_path(self):
        p = getattr(self, '_conf_path', None)
        if p is None:
            c = self.config.wowza
            p = self._conf_path = os.path.join(c.root_path, 'conf')
        return p
    def build_filename(self, *args):
        return os.path.join(self.conf_path, *args)
    def do_action(self, **kwargs):
        c = self.config.wowza
        for key in ['server_license', 'users', 'publish_users', 'conf_files']:
            if key in kwargs:
                c.setdefault(key, kwargs[key])
        if c.get('server_license'):
            self.set_server_license()
        if c.get('users'):
            self.set_users()
        if c.get('publish_users'):
            self.set_publish_users()
        if c.get('conf_files'):
            self.copy_files()
    def set_server_license(self):
        c = self.config.wowza
        fn = self.build_filename('Server.license')
        with open(fn, 'w') as f:
            f.write(c.server_license)
    def set_users(self):
        c = self.config.wowza
        fn = self.build_filename('admin.password')
        lines = []
        keys = ['name', 'password', 'group']
        for user in c.users:
            user.setdefault('group', 'admin')
            lines.append(' '.join([user.get(key) for key in keys]))
        with open(fn, 'w') as f:
            f.write('\n'.join(lines))
    def set_publish_users(self):
        c = self.config.wowza
        fn = self.build_filename('publish.password')
        lines = []
        keys = ['name', 'password']
        for user in c.publish_users:
            lines.append(' '.join([user.get(key) for key in keys]))
        with open(fn, 'w') as f:
            f.write('\n'.join(lines))
    def copy_files(self):
        c = self.config.wowza
        for file_info in c.conf_files:
            content = file_info.get('content')
            if content is None:
                url = file_info['url']
                r = requests.get(url)
                content = r.content
            fn = os.path.join(c.root_path, file_info['path'])
            with open(fn, 'wb') as f:
                f.write(content)
