#! /usr/bin/env python

import os
import time
import datetime
import threading
import collections
import traceback
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
    
def get_fields(field_names=None):
    if field_names is None:
        field_names = get_field_names()
    elif isinstance(field_names, basestring):
        field_names = field_names.split(',')
    if 'timestamp' not in field_names:
        field_names = ['timestamp'] + field_names
    field_types = ['REAL' if fname == 'timestamp' else 'TEXT' for fname in field_names]
    return field_names, field_types
    
class DbLogger(object):
    def __init__(self, **kwargs):
        filename = kwargs.get('filename')
        if filename is None:
            filename = os.path.expanduser('~/wowzalog.db')
        field_names = kwargs.get('field_names')
        field_types = kwargs.get('field_types')
        if field_types is None:
            field_names, field_types = get_fields(field_names)
        self.field_names, self.field_types = field_names, field_types
        self.filename = filename
        self.table_name = None
        self.queue = collections.deque()
        self.need_write = threading.Event()
        self.entry_lock = threading.Lock()
        self.db_thread = DbThread(self)
        self.db_thread.start()
        if self.db_thread.exception is None:
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
        fnames, ftypes = self.field_names, self.field_types
        field_str = ', '.join(['"%s" %s' % f for f in zip(fnames, ftypes)])
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
        v = ','.join(['?'] * len(self.field_names))
        stmt = 'insert into %s values (%s)' % (self.table_name, v)
        entry = line.split('\t')
        i = self.field_names.index('timestamp')
        entry.insert(i, ts)
        with self.entry_lock:
            self.queue.append((stmt, entry))
            self.need_write.set()
    def commit_entries(self, *entries):
        conn = self.get_connection()
        with conn:
            for stmt, entry in entries:
                conn.execute(stmt, entry)
        
class DbThread(threading.Thread):
    def __init__(self, db_logger):
        super(DbThread, self).__init__()
        self.db_logger = db_logger
        self._running = threading.Event()
        self._stopped = threading.Event()
        self.exception = None
    def run(self):
        self._running.set()
        need_write = self.db_logger.need_write
        while self._running.is_set():
            need_write.wait()
            if not self._running.is_set():
                break
            try:
                self.commit_entries()
            except Exception as e:
                self.exception = e
                self.exception_tb = traceback.format_exc()
                self._running.clear()
                print(self.exception_tb)
        print('DbThread stopped')
        self._stopped.set()
    def stop(self):
        print('DbThread stopping..')
        self._running.clear()
        self.db_logger.need_write.set()
        self._stopped.wait()
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
        self.db = DbLogger(**kwargs)
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
        
def main(**kwargs):
    server = WowzaUDPServer(**kwargs)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server, server_thread

def main_loop(**kwargs):
    server, server_thread = main(**kwargs)
    while True:
        try:
            time.sleep(1.)
        except KeyboardInterrupt:
            break
    server.shutdown()
    server.server_close()
    return server, server_thread

def test(test_sock=False, **kwargs):
    import socket
    num_entries = 10
    kwargs.setdefault('field_names', 'date,time,tz,x_event,x_category,x_severity,x_status,x_ctx,x_comment,x_vhost,x_app,x_appinst,x_duration,s_ip,s_port,s_uri,c_ip,c_proto,c_referrer,c_user_agent,c_client_id,cs_bytes,sc_bytes,x_stream_id,x_spos,cs_stream_bytes,sc_stream_bytes,x_sname,x_sname_query,x_file_name,x_file_ext,x_file_size,x_file_length,x_suri,x_suri_stem,x_suri_query,cs_uri_stem,cs_uri_query')
    server, server_thread = main(**kwargs)
    def build_entry(i):
        ts = time.time()
        dt = datetime.datetime.utcfromtimestamp(ts)
        e = ['-'] * (len(server.db.field_names) - 1)
        e[0] = dt.strftime('%Y-%m-%d')
        e[1] = dt.strftime('%H:%M:%S')
        e[2] = 'UTC'
        e[3] = str(i)
        e = '\t'.join(e)
        return e + '\n', ts
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = server.server_address
    i = 0
    try:
        while i < num_entries:
            e, ts = build_entry(i)
            print('adding entry %s' % (i))
            if test_sock:
                sock.sendto(e, addr)
            else:
                server.add_entry(e, ts)
            time.sleep(.2)
            i += 1
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    main_loop()
