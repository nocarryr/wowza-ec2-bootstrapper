import json

import requests

from wowza_ec2_bootstrapper.config import config

class BaseAction(object):
    all_actions = []
    action_iter = None
    all_complete = False
    config = config
    def __init__(self, **kwargs):
        if not hasattr(self, 'action_name'):
            self.action_name = kwargs['action_name']
        self.kwargs = kwargs
        self._completed = False
        self._failed = False
    @classmethod
    def create(cls, **kwargs):
        action_name = kwargs.get('action_name')
        def find_class(base_cls):
            if hasattr(base_cls, 'name') and base_cls.name == action_name:
                return base_cls
            if base_cls.__name__ == action_name:
                return base_cls
            for _cls in base_cls.__subclasses__():
                r = find_class(_cls)
                if r is not None:
                    return r
            return None
        cls = find_class(BaseAction)
        if cls is None:
            raise Exception('Could not locate class for action %s' % (action_name))
        action = cls(**kwargs)
        BaseAction.all_actions.append(action)
        return action
    def __call__(self):
        if BaseAction.action_iter is None:
            BaseAction.action_iter = iter(BaseAction.all_actions)
        elif self.__class__ is not BaseAction:
            r = self.do_action(**self.kwargs)
            if not r:
                self._failed = True
            self._completed = True
        try:
            next_action = next(BaseAction.action_iter)
        except StopIteration:
            next_action = None
            BaseAction.all_complete = True
        if next_action is not None:
            next_action()
    def do_action(self):
        raise NotImplementedError('must be defined in subclass')
    @classmethod
    def to_json(cls, **kwargs):
        l = []
        for action in cls.all_actions:
            l.append(action._serialize)
        d = {'actions':l}
        return json.dumps(d, **kwargs)
    @classmethod
    def from_json(cls, **kwargs):
        s = kwargs.get('json')
        fn = kwargs.get('filename')
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
            data = json.loads(s)
        for action_kwargs in data['actions']:
            cls.create(**action_kwargs)
        return BaseAction
    def _serialize(self):
        action_name = getattr(self, 'action_name', None)
        if not action_name:
            action_name = self.__class__.__name__
        d = {'action_name':action_name}
        d.update(self.kwargs)
        return d
