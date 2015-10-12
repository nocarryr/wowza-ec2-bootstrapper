import os

import boto3
import botocore

from wowza_ec2_bootstrapper.actions import BaseAction

class LogSyncBase(BaseAction):
    @property
    def s3(self):
        s3 = getattr(self, '_s3', None)
        if s3 is None:
            s3 = self._s3 = boto3.resource('s3')
        return s3
    @property
    def bucket(self):
        b = getattr(self, '_bucket', None)
        if b is None:
            b = self._bucket = self.get_bucket()
        return b
    def get_bucket(self):
        bname = self.kwargs.get('bucket')
        if bname is not None:
            return bname
        bname = self.config.log_bucket_name
        return self.s3.Bucket(bname)
    @property
    def log_path(self):
        p = getattr(self, '_log_path', None)
        if p is None:
            p = self._log_path = self.get_log_path()
        return p
    def get_log_path(self):
        p = self.kwargs.get('log_path')
        if p is not None:
            return p
        conf = self.config.get('wowza')
        if conf is None:
            conf = self.config.add_config('wowza')
        p = conf.get('log_path')
        if p is None:
            wms_root = conf.get('root_path')
            if wms_root is None:
                ## TODO: use env vars?
                wms_root = '/usr/local/WowzaStreamingEngine'
                conf.wms_root = wms_root
            p = os.path.join(wms_root, 'logs')
            conf.log_path = p
        return p
    def iter_local(self):
        p = self.log_path
        for fn in os.listdir(p):
            yield os.path.join(p, fn)
    def iter_remote(self):
        return self.bucket.objects.all()
    def get_remote_object(self, filename):
        keyname = os.path.basename(filename)
        return self.s3.Object(self.bucket.name, keyname)
    def remote_exists(self, filename=None, obj=None):
        if obj is None:
            obj = self.get_remote_object(filename)
        exists = True
        try:
            obj.load()
        except botocore.exceptions.ClientError:
            exists = False
        return exists
    def get_remote(self, filename):
        object = self.get_remote_object(filename)
        r = object.get()
        data = r['Body'].read()
        ## TODO: handle permissions/owner
        with open(filename, 'wb') as f:
            f.write(data)
    def put_remote(self, filename):
        keyname = os.path.basename(filename)
        data = open(filename, 'rb')
        self.bucket.put_object(
            Key=keyname, 
            Body=data, 
            ContentType='text/plain', 
        )
    
class LogSyncUp(LogSyncBase):
    def do_action(self, **kwargs):
        for local_fn in self.iter_local():
            obj = self.get_remote_object(local_fn)
            if self.remote_exists(obj=obj):
                if local_fn.endswith('.log'):
                    continue
            self.put_remote(local_fn)
        return True
        
class LogSyncDown(LogSyncBase):
    def do_action(self, **kwargs):
        p = self.log_path
        for obj in self.iter_remote():
            local_fn = os.path.join(p, obj.key)
            if os.path.exists(local_fn):
                if not local_fn.endswith('.log'):
                    continue
            self.get_remote(local_fn)
        return True
        
