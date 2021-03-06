import os
import stat

import requests

from wowza_ec2_bootstrapper.actions import BaseAction

class CustomScript(BaseAction):
    action_fields = dict(
        filename={
            'required':True, 
            'help':'Local filename to write the script to', 
        }, 
        contents={
            'required':['contents', 'url'], 
            'help':'The script contents (as string)', 
        }, 
        url={
            'required':['contents', 'url'], 
            'help':'URL to retrieve the script contents', 
        }, 
    )
    def do_action(self, **kwargs):
        filename = os.path.expanduser(kwargs.get('filename'))
        contents = kwargs.get('contents')
        if contents is None:
            contents = self.get_contents_from_url(**kwargs)
        with open(filename, 'w') as f:
            f.write(contents)
        fmode = os.stat(filename).st_mode
        fmode |= stat.S_IXUSR | stat.S_IXGRP
        os.chmod(filename, fmode)
        return True
    def get_contents_from_url(self, **kwargs):
        url = kwargs.get('url')
        r = requests.get(url)
        assert r.status_code == 200
        return r.contents
