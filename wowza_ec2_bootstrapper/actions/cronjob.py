from crontab import CronTab

from wowza_ec2_bootstrapper.actions import BaseAction

class CronJob(BaseAction):
    cron_fields = ['minute', 'hour', 'dom', 'mon', 'dow']
    action_fields = dict(
        user={
            'required':False, 
            'default':None, 
            'help':'User to attach the crontab to (Leave blank for current user)', 
        }, 
        fields={
            'required':True, 
            'help':'Time fields for the cron job (m h dom mon dow)', 
        }, 
        command={
            'required':True, 
            'help':'The command to be inserted', 
        }
    )
    def do_action(self, **kwargs):
        user = kwargs.get('user')
        if user == 'root':
            return self.add_system_cron(**kwargs)
        if user is None:
            kwargs['user'] = True
        return self.add_user_cron(**kwargs)
    def cron_slice_to_fields(self, job):
        values = []
        for field in self.cron_fields:
            values.append(getattr(job, field).render())
        return ' '.join(values)
    def add_cron_command(self, cron, **kwargs):
        fields = kwargs.get('fields')
        cmd = kwargs.get('command')
        if isinstance(fields, dict):
            _fields = []
            for fname in self.cron_fields:
                fval = fields.get(fname, '*')
                _fields.append(fval)
            fields = _fields
        if isinstance(fields, list):
            fields = ' '.join(fields)
        for existing_job in cron.find_command(cmd):
            if not existing_job.is_enabled():
                continue
            if self.cron_slice_to_fields(existing_job) == fields:
                return True
        job = cron.new(command=cmd)
        job.setall(fields)
        return job
    def add_user_cron(self, **kwargs):
        cron = CronTab(user=kwargs.get('user'))
        self.add_cron_command(cron, **kwargs)
        cron.write()
        return True
    def add_system_cron(self, **kwargs):
        cronfile = kwargs.get('filename', '/etc/crontab')
        cron = CronTab(tabfile=cronfile, user=False)
        job = self.add_cron_command(cron, **kwargs)
        job.user = 'root'
        cron.write()
        return True
