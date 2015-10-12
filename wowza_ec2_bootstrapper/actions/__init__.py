from wowza_ec2_bootstrapper.config import config


from base import BaseAction
from associate_eip import AssociateEIP
from logsync import LogSyncUp, LogSyncDown
from set_config import SetConfig

def build_from_config():
    return BaseAction.from_json(data=config.action_data['actions'])
    
def save_to_config():
    l = []
    for action in BaseAction.all_actions:
        l.append(action._serialize())
    config.action_data['actions'] = l
    config.to_json(indent=2)

if config.action_data.get('actions'):
    build_from_config()
