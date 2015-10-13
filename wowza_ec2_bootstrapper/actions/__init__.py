from wowza_ec2_bootstrapper.config import config


from base import BaseAction
from associate_eip import AssociateEIP
from logsync import LogSyncUp, LogSyncDown
from set_config import SetConfig
from customscript import CustomScript
from cronjob import CronJob

def build_from_config(_config=None):
    if _config is None:
        _config = config
    return BaseAction.from_json(data=_config.action_data['actions'])
    
def save_to_config(_config=None):
    if _config is None:
        _config = config
    l = []
    for action in BaseAction.all_actions:
        l.append(action._serialize())
    _config.action_data['actions'] = l
    _config.to_json(indent=2)

if config.action_data.get('actions'):
    build_from_config()
