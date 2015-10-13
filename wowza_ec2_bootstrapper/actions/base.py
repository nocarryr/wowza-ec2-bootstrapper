import json

import requests

from wowza_ec2_bootstrapper.config import config


class BaseAction(object):
    __action_abstract = True
    def __init__(self, **kwargs):
        self._root_action = kwargs.get('_root_action', self)
        if self._root_action is self:
            self.all_actions = []
            self.action_iter = None
            self.all_complete = False
            self.config = kwargs.get('config', config)
        else:
            if not hasattr(self, 'action_name'):
                self.action_name = kwargs['action_name']
            self.kwargs = kwargs
            self._completed = False
            self._failed = False
        self._root_action.all_actions.append(self)
    @classmethod
    def get_action_fields(cls, fields=None):
        if fields is None:
            is_root = True
            fields = {cls:getattr(cls, 'action_fields', {})}
        else:
            is_root = False
            my_fields = {}
            for _cls, _fields in fields.items():
                if not issubclass(cls, _cls):
                    continue
                my_fields.update(_fields)
            my_fields.update(getattr(cls, 'action_fields', {}))
            fields[cls] = my_fields
        for _cls in cls.__subclasses__():
            _cls.get_action_fields(fields)
        if not is_root:
            return fields
        cleaned_fields = {}
        for _cls, _fields in fields.items():
            if getattr(_cls, '_%s__action_abstract' % (_cls.__name__), False):
                continue
            key = getattr(_cls, 'action_name', _cls.__name__)
            cleaned_fields[key] = _fields
        return cleaned_fields
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
        return action
    def __call__(self):
        if self._root_action.action_iter is None:
            self._root_action.action_iter = iter(self._root_action.all_actions)
        elif self.__class__ is not BaseAction:
            r = self.do_action(**self.kwargs)
            if not r:
                self._failed = True
            self._completed = True
        try:
            next_action = next(self._root_action.action_iter)
        except StopIteration:
            next_action = None
            self._root_action.all_complete = True
        if next_action is not None:
            next_action()
    def do_action(self):
        raise NotImplementedError('must be defined in subclass')
    def to_json(self, **kwargs):
        l = []
        for action in self._root_action.all_actions:
            l.append(action._serialize)
        d = {'actions':l}
        return json.dumps(d, **kwargs)
    @classmethod
    def from_json(cls, **kwargs):
        s = kwargs.get('json')
        fn = kwargs.get('filename')
        url = kwargs.get('url')
        data = kwargs.get('data')
        if data is None:
            if s is None:
                if fn is not None:
                    with open(fn, 'r') as f:
                        s = f.read()
                elif url is not None:
                    r = requests.get(url)
                    data = r.json()
            if data is None:
                data = json.loads(s)
        if isinstance(data, dict):
            data = data['actions']
        root_action = None
        for action_kwargs in data:
            if root_action is not None:
                action_kwargs.setdefault('_root_action', root_action)
            obj = cls.create(**action_kwargs)
            root_action = obj._root_action
        return root_action
    def _serialize(self):
        action_name = getattr(self, 'action_name', None)
        if not action_name:
            action_name = self.__class__.__name__
        d = {'action_name':action_name}
        d.update(self.kwargs)
        return d
