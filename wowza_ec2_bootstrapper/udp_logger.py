#! /usr/bin/env python

import os
import time
import datetime
import threading
import collections
from SocketServer import UDPServer, BaseRequestHandler
import sqlite3

WOWZA_ROOT = '/usr/local/WowzaStreamingEngine'

def get_field_names():
    logconf = os.path.join(WOWZA_ROOT, 'conf', 'log4j.properties')
    with open(logconf, 'r') as f:
        s = f.read()
    for line in s.splitlines():
        if line.startswith('#'):
            continue
        if 'serverAccessUDP' not in line:
            continue
        if 'layout.Fields=' not in line:
            continue
        fields = line.split('=')[1]
        fields = [field.strip() for field in fields.split(',')]
        fields = ['_'.join(field.split('-')) for field in fields]
        return fields
    
def get_fields():
    field_names = ['timestamp']
    field_names.extend(get_field_names())
    field_types = ['REAL' if fname == 'timestamp' else 'TEXT' for fname in field_names]
    return zip(field_names, field_types)
    
class DbLogger(object):
    def __init__(self, **kwargs):
        filename = kwargs.get('filename')
        if filename is None:
            filename = os.path.expanduser('~/wowzalog.db')
        fields = kwargs.get('fields')
        if fields is None:
            fields = get_fields()
        self.fields = fields
        self.filename = filename
        self.table_name = None
        self.queue = collections.deque()
        self.need_write = threading.Event()
        self.entry_lock = threading.Lock()
        self.db_thread = DbThread(self)
        self.db_thread.start()
        self.db_thread._running.wait()
    def stop(self):
        self.db_thread.stop()
    def get_connection(self):
        return sqlite3.connect(self.filename)
    def create_table(self, tbl_name=None):
        if tbl_name is None:
            now = datetime.datetime.utcnow()
            tbl_name = now.strftime('"%Y%m%d_%H%M%S"')
        if tbl_name == self.table_name:
            return
        self.table_name = tbl_name
        field_str = ','.join([' '.join(f) for f in self.fields])
        stmt = 'create table %s (%s)' % (tbl_name, field_str)
        print(stmt)
        conn = self.get_connection()
        with conn:
            conn.execute(stmt)
    def add_entry(self, line, ts=None):
        if ts is None:
            ts = time.time()
        t = self.db_thread
        if not t._running.is_set() and self.need_write.is_set():
            return
        if self.table_name is None:
            self.create_table()
        line = line.strip('\n')
        v = ','.join(['?'] * len(self.fields))
        stmt = 'insert into %s values (%s)' % (self.table_name, v)
        entry = [ts]
        entry.extend(line.split('\t'))
        with self.entry_lock:
            self.queue.append((stmt, entry))
            self.need_write.set()
    def commit_entries(self, *entries):
        conn = self.get_connection()
        with conn:
            for stmt, entry in entries:
                conn.exectute(stmt, entry)
        
class DbThread(threading.Thread):
    def __init__(self, db_logger):
        super(DbThread, self).__init__()
        self.db_logger = db_logger
        self._running = threading.Event()
        self._stopped = threading.Event()
    def run(self):
        self._running.set()
        need_write = self.db_logger.need_write
        while self._running.is_set():
            need_write.wait()
            if not self._running.is_set():
                break
            self.commit_entries()
        self._stopped.set()
    def stop(self):
        print('DbThread stopping..')
        self._running.clear()
        self.db_logger.need_write.set()
        self._stopped.wait()
        print('DbThread stopped')
    def commit_entries(self):
        db = self.db_logger
        def get_entries():
            entries = []
            while True:
                with db.entry_lock:
                    try:
                        entry = db.queue.popleft()
                    except IndexError:
                        entry = None
                    if entry is None:
                        if self._running.is_set():
                            db.need_write.clear()
                        break
                    else:
                        entries.append(entry)
            return entries
        while True:
            entries = get_entries()
            if not len(entries):
                break
            db.commit_entries(*entries)
        
class WowzaUDPServer(UDPServer):
    def __init__(self, **kwargs):
        host = kwargs.get('host', '127.0.0.1')
        port = int(kwargs.get('port', 8881))
        UDPServer.__init__(self, (host, port), WowzaHandler)
        self.db = DbLogger()
    def add_entry(self, line, ts=None):
        self.db.add_entry(line, ts)
    def server_close(self):
        UDPServer.server_close(self)
        self.db.stop()
    
class WowzaHandler(BaseRequestHandler):
    def handle(self):
        now = time.time()
        data = self.request[0]
        print(data)
        self.server.add_entry(data, ts=now)
        
if __name__ == '__main__':
    server = WowzaUDPServer()
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    while True:
        try:
            time.sleep(1.)
        except KeyboardInterrupt:
            break
    server.shutdown()
    server.server_close()
