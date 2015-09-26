from wowza_ec2_bootstrapper.config import config

class BaseAction(object):
    all_actions = []
    action_iter = None
    all_complete = False
    config = config
    def __init__(self, **kwargs):
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
        r = self.do_action(**self.kwargs)
        if not r:
            self._failed = True
        self._completed = True
        if BaseAction.action_iter is None:
            BaseAction.action_iter = iter(BaseAction.all_actions)
        try:
            next_action = next(BaseAction.action_iter)
        except StopIteration:
            next_action = None
            BaseAction.all_complete = True
        if next_action is not None:
            next_action()
    def do_action(self):
        raise NotImplementedError('must be defined in subclass')
    
