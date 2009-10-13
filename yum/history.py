#!/usr/bin/python -t
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Copyright 2009 Red Hat
#
# James Antill <james@fedoraproject.org>

import time
import os, os.path
import glob
from weakref import proxy as weakref

from sqlutils import sqlite, executeSQL
import yum.misc as misc
import yum.constants
from yum.constants import *
from yum.packages import YumInstalledPackage, YumAvailablePackage, PackageObject
from yum.i18n import to_unicode


_history_dir = '/var/lib/yum/history'

# NOTE: That we don't list TS_FAILED, because pkgs shouldn't go into the
#       transaction with that. And if they come out with that we don't want to
#       match them to anything anyway.
_stcode2sttxt = {TS_UPDATE : 'Update',
                 TS_UPDATED : 'Updated', 
                 TS_ERASE: 'Erase',
                 TS_INSTALL: 'Install', 
                 TS_TRUEINSTALL : 'True-Install',
                 TS_OBSOLETED: 'Obsoleted',
                 TS_OBSOLETING: 'Obsoleting'}

_sttxt2stcode = {'Update' : TS_UPDATE,
                 'Updated' : TS_UPDATED, 
                 'Erase' : TS_ERASE,
                 'Install' : TS_INSTALL, 
                 'True-Install' : TS_TRUEINSTALL,
                 'Dep-Install' : TS_INSTALL,
                 'Reinstall' : TS_INSTALL, # Broken
                 'Downgrade' : TS_INSTALL, # Broken
                 'Downgraded' : TS_INSTALL, # Broken
                 'Obsoleted' : TS_OBSOLETED,
                 'Obsoleting' : TS_OBSOLETING}

# ---- horrible Copy and paste from sqlitesack ----
def _sql_esc(pattern):
    """ Apply SQLite escaping, if needed. Returns pattern and esc. """
    esc = ''
    if "_" in pattern or "%" in pattern:
        esc = ' ESCAPE "!"'
        pattern = pattern.replace("!", "!!")
        pattern = pattern.replace("%", "!%")
        pattern = pattern.replace("_", "!_")
    return (pattern, esc)

def _sql_esc_glob(patterns):
    """ Converts patterns to SQL LIKE format, if required (or gives up if
        not possible). """
    ret = []
    for pattern in patterns:
        if '[' in pattern: # LIKE only has % and _, so [abc] can't be done.
            return []      # So Load everything

        # Convert to SQL LIKE format
        (pattern, esc) = _sql_esc(pattern)
        pattern = pattern.replace("*", "%")
        pattern = pattern.replace("?", "_")
        ret.append((pattern, esc))
    return ret

def _setupHistorySearchSQL(patterns=None, ignore_case=False):
    """Setup need_full and patterns for _yieldSQLDataList, also see if
       we can get away with just using searchNames(). """

    if patterns is None:
        patterns = []

    fields = ['name', 'sql_nameArch', 'sql_nameVerRelArch',
              'sql_nameVer', 'sql_nameVerRel',
              'sql_envra', 'sql_nevra']
    need_full = False
    for pat in patterns:
        if yum.misc.re_full_search_needed(pat):
            need_full = True
            break

    pat_max = PATTERNS_MAX
    if not need_full:
        fields = ['name']
        pat_max = PATTERNS_INDEXED_MAX
    if len(patterns) > pat_max:
        patterns = []
    if ignore_case:
        patterns = _sql_esc_glob(patterns)
    else:
        tmp = []
        need_glob = False
        for pat in patterns:
            if misc.re_glob(pat):
                tmp.append((pat, 'glob'))
                need_glob = True
            else:
                tmp.append((pat, '='))
        if not need_full and not need_glob and patterns:
            return (need_full, patterns, fields, True)
        patterns = tmp
    return (need_full, patterns, fields, False)
# ---- horrible Copy and paste from sqlitesack ----

class YumHistoryPackage(PackageObject):

    def __init__(self, name, arch, epoch, version, release, checksum):
        self.name    = name
        self.version = version
        self.release = release
        self.epoch   = epoch
        self.arch    = arch
        self.pkgtup = (self.name, self.arch,
                       self.epoch, self.version, self.release)
        if checksum is None:
            self._checksums = [] # (type, checksum, id(0,1)
        else:
            chk = checksum.split(':')
            self._checksums = [(chk[0], chk[1], 0)] # (type, checksum, id(0,1))

class YumHistoryTransaction:
    """ Holder for a history transaction. """

    def __init__(self, history, row):
        self._history = weakref(history)

        self.tid              = row[0]
        self.beg_timestamp    = row[1]
        self.beg_rpmdbversion = row[2]
        self.end_timestamp    = row[3]
        self.end_rpmdbversion = row[4]
        self.loginuid         = row[5]
        self.return_code      = row[6]

        self._loaded_TW = None
        self._loaded_TD = None

        self._loaded_ER = None
        self._loaded_OT = None

        self.altered_lt_rpmdb = None
        self.altered_gt_rpmdb = None

    def __cmp__(self, other):
        if other is None:
            return 1
        ret = cmp(self.beg_timestamp, other.beg_timestamp)
        if ret: return -ret
        ret = cmp(self.end_timestamp, other.end_timestamp)
        if ret: return ret
        ret = cmp(self.tid, other.tid)
        return -ret

    def _getTransWith(self):
        if self._loaded_TW is None:
            self._loaded_TW = sorted(self._history._old_with_pkgs(self.tid))
        return self._loaded_TW
    def _getTransData(self):
        if self._loaded_TD is None:
            self._loaded_TD = sorted(self._history._old_data_pkgs(self.tid))
        return self._loaded_TD

    trans_with = property(fget=lambda self: self._getTransWith())
    trans_data = property(fget=lambda self: self._getTransData())

    def _getErrors(self):
        if self._loaded_ER is None:
            self._loaded_ER = self._history._load_errors(self.tid)
        return self._loaded_ER
    def _getOutput(self):
        if self._loaded_OT is None:
            self._loaded_OT = self._history._load_output(self.tid)
        return self._loaded_OT

    errors     = property(fget=lambda self: self._getErrors())
    output     = property(fget=lambda self: self._getOutput())

class YumHistory:
    """ API for accessing the history sqlite data. """

    def __init__(self, root='/', db_path=_history_dir):
        self._conn = None
        
        self.conf = yum.misc.GenericHolder()
        self.conf.db_path  = os.path.normpath(root + '/' + db_path)
        self.conf.writable = False

        if not os.path.exists(self.conf.db_path):
            try:
                os.makedirs(self.conf.db_path)
            except (IOError, OSError), e:
                # some sort of useful thing here? A warning?
                return
            self.conf.writable = True
        else:
            if os.access(self.conf.db_path, os.W_OK):
                self.conf.writable = True

        DBs = glob.glob('%s/history-*-*-*.sqlite' % self.conf.db_path)
        self._db_file = None
        for d in reversed(sorted(DBs)):
            fname = os.path.basename(d)
            fname = fname[len("history-"):-len(".sqlite")]
            pieces = fname.split('-', 4)
            if len(pieces) != 3:
                continue
            try:
                map(int, pieces)
            except ValueError:
                continue

            self._db_file = d
            break

        if self._db_file is None:
            self._create_db_file()

    def __del__(self):
        self.close()

    def _get_cursor(self):
        if self._conn is None:
            self._conn = sqlite.connect(self._db_file)
        return self._conn.cursor()
    def _commit(self):
        return self._conn.commit()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _pkgtup2pid(self, pkgtup, checksum=None):
        cur = self._get_cursor()
        executeSQL(cur, """SELECT pkgtupid, checksum FROM pkgtups
                           WHERE name=? AND arch=? AND
                                 epoch=? AND version=? AND release=?""", pkgtup)
        for sql_pkgtupid, sql_checksum in cur:
            if checksum is None and sql_checksum is None:
                return sql_pkgtupid
            if checksum is None:
                continue
            if sql_checksum is None:
                continue
            if checksum == sql_checksum:
                return sql_pkgtupid
        
        (n,a,e,v,r) = pkgtup
        (n,a,e,v,r) = (to_unicode(n),to_unicode(a),
                       to_unicode(e),to_unicode(v),to_unicode(r))
        if checksum is not None:
            res = executeSQL(cur,
                             """INSERT INTO pkgtups
                                (name, arch, epoch, version, release, checksum)
                                VALUES (?, ?, ?, ?, ?, ?)""", (n,a,e,v,r,
                                                               checksum))
        else:
            res = executeSQL(cur,
                             """INSERT INTO pkgtups
                                (name, arch, epoch, version, release)
                                VALUES (?, ?, ?, ?, ?)""", (n,a,e,v,r))
        return cur.lastrowid
    def _apkg2pid(self, po):
        csum = po.returnIdSum()
        if csum is not None:
            csum = "%s:%s" % (str(csum[0]), str(csum[1]))
        return self._pkgtup2pid(po.pkgtup, csum)
    def _ipkg2pid(self, po):
        csum = None
        yumdb = po.yumdb_info
        if 'checksum_type' in yumdb and 'checksum_type' in yumdb:
            csum = "%s:%s" % (yumdb.checksum_type, yumdb.checksum_data)
        return self._pkgtup2pid(po.pkgtup, csum)
    def pkg2pid(self, po):
        if isinstance(po, YumInstalledPackage):
            return self._ipkg2pid(po)
        if isinstance(po, YumAvailablePackage):
            return self._apkg2pid(po)
        return self._pkgtup2pid(po.pkgtup, None)

    @staticmethod
    def txmbr2state(txmbr):
        state = None
        if txmbr.output_state in (TS_INSTALL, TS_TRUEINSTALL):
            if hasattr(txmbr, 'reinstall'):
                state = 'Reinstall'
            elif txmbr.downgrades:
                state = 'Downgrade'
        if txmbr.output_state == TS_ERASE:
            if txmbr.downgraded_by:
                state = 'Downgraded'
        if state is None:
            state = _stcode2sttxt.get(txmbr.output_state)
            if state == 'Install' and txmbr.isDep:
                state = 'Dep-Install'
        return state

    def trans_with_pid(self, pid):
        cur = self._get_cursor()
        res = executeSQL(cur,
                         """INSERT INTO trans_with_pkgs
                         (tid, pkgtupid)
                         VALUES (?, ?)""", (self._tid, pid))
        return cur.lastrowid

    def trans_data_pid_beg(self, pid, state):
        assert state is not None
        if not hasattr(self, '_tid') or state is None:
            return # Not configured to run
        cur = self._get_cursor()
        res = executeSQL(cur,
                         """INSERT INTO trans_data_pkgs
                         (tid, pkgtupid, state)
                         VALUES (?, ?, ?)""", (self._tid, pid, state))
        return cur.lastrowid
    def trans_data_pid_end(self, pid, state):
        # State can be none here, Eg. TS_FAILED from rpmtrans
        if not hasattr(self, '_tid') or state is None:
            return # Not configured to run

        cur = self._get_cursor()
        res = executeSQL(cur,
                         """UPDATE trans_data_pkgs SET done = ?
                         WHERE tid = ? AND pkgtupid = ? AND state = ?
                         """, ('TRUE', self._tid, pid, state))
        self._commit()
        return cur.lastrowid

    def beg(self, rpmdb_version, using_pkgs, txmbrs):
        cur = self._get_cursor()
        res = executeSQL(cur,
                         """INSERT INTO trans_beg
                            (timestamp, rpmdb_version, loginuid)
                            VALUES (?, ?, ?)""", (int(time.time()),
                                                    str(rpmdb_version),
                                                    yum.misc.getloginuid()))
        self._tid = cur.lastrowid

        for pkg in using_pkgs:
            pid = self._ipkg2pid(pkg)
            self.trans_with_pid(pid)
        
        for txmbr in txmbrs:
            pid   = self.pkg2pid(txmbr.po)
            state = self.txmbr2state(txmbr)
            self.trans_data_pid_beg(pid, state)
        
        self._commit()

    def _log_errors(self, errors):
        cur = self._get_cursor()
        for error in errors:
            error = to_unicode(error)
            executeSQL(cur,
                       """INSERT INTO trans_error
                          (tid, msg) VALUES (?, ?)""", (self._tid, error))
        self._commit()

    def log_scriptlet_output(self, data, msg):
        """ Note that data can be either a real pkg. ... or not. """
        if msg is None or not hasattr(self, '_tid'):
            return # Not configured to run

        cur = self._get_cursor()
        for error in msg.split('\n'):
            error = to_unicode(error)
            executeSQL(cur,
                       """INSERT INTO trans_script_stdout
                          (tid, line) VALUES (?, ?)""", (self._tid, error))
        self._commit()

    def _load_errors(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT msg FROM trans_error
                      WHERE tid = ?
                      ORDER BY mid ASC""", (tid,))
        ret = []
        for row in cur:
            ret.append(row[0])
        return ret

    def _load_output(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT line FROM trans_script_stdout
                      WHERE tid = ?
                      ORDER BY lid ASC""", (tid,))
        ret = []
        for row in cur:
            ret.append(row[0])
        return ret

    def end(self, rpmdb_version, return_code, errors=None):
        assert return_code or not errors
        cur = self._get_cursor()
        res = executeSQL(cur,
                         """INSERT INTO trans_end
                            (tid, timestamp, rpmdb_version, return_code)
                            VALUES (?, ?, ?, ?)""", (self._tid,int(time.time()),
                                                     str(rpmdb_version),
                                                     return_code))
        self._commit()
        if not return_code:
            #  Simple hack, if the transaction finished. Note that this
            # catches the erase cases (as we still don't get pkgtups for them),
            # Eg. Updated elements.
            executeSQL(cur,
                       """UPDATE trans_data_pkgs SET done = ?
                          WHERE tid = ?""", ('TRUE', self._tid,))
            self._commit()
        if errors is not None:
            self._log_errors(errors)
        del self._tid

    def _old_with_pkgs(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release, checksum
                      FROM trans_with_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE tid = ?
                      ORDER BY name ASC, epoch ASC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5])
            ret.append(obj)
        return ret
    def _old_data_pkgs(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release,
                             checksum, done, state
                      FROM trans_data_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE tid = ?
                      ORDER BY name ASC, epoch ASC, state DESC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5])
            obj.done     = row[6] == 'TRUE'
            obj.state    = row[7]
            obj.state_installed = None
            if _sttxt2stcode[obj.state] in TS_INSTALL_STATES:
                obj.state_installed = True
            if _sttxt2stcode[obj.state] in TS_REMOVE_STATES:
                obj.state_installed = False
            ret.append(obj)
        return ret

    def old(self, tids=[], limit=None, complete_transactions_only=False):
        """ Return a list of the last transactions, note that this includes
            partial transactions (ones without an end transaction). """
        cur = self._get_cursor()
        sql =  """SELECT tid,
                         trans_beg.timestamp AS beg_ts,
                         trans_beg.rpmdb_version AS beg_rv,
                         trans_end.timestamp AS end_ts,
                         trans_end.rpmdb_version AS end_rv,
                         loginuid, return_code
                  FROM trans_beg JOIN trans_end USING(tid)"""
        # NOTE: sqlite doesn't do OUTER JOINs ... *sigh*. So we have to do it
        #       ourself.
        if not complete_transactions_only:
            sql =  """SELECT tid,
                             trans_beg.timestamp AS beg_ts,
                             trans_beg.rpmdb_version AS beg_rv,
                             NULL, NULL,
                             loginuid, NULL
                      FROM trans_beg"""
        params = None
        if tids and len(tids) <= yum.constants.PATTERNS_INDEXED_MAX:
            params = tids = list(set(tids))
            sql += " WHERE tid IN (%s)" % ", ".join(['?'] * len(tids))
        sql += " ORDER BY beg_ts DESC, tid ASC"
        if limit is not None:
            sql += " LIMIT " + str(limit)
        executeSQL(cur, sql, params)
        ret = []
        tid2obj = {}
        for row in cur:
            if tids and len(tids) > yum.constants.PATTERNS_INDEXED_MAX:
                if row[0] not in tids:
                    continue
            obj = YumHistoryTransaction(self, row)
            tid2obj[row[0]] = obj
            ret.append(obj)

        sql =  """SELECT tid,
                         trans_end.timestamp AS end_ts,
                         trans_end.rpmdb_version AS end_rv,
                         return_code
                  FROM trans_end"""
        params = tid2obj.keys()
        if len(params) > yum.constants.PATTERNS_INDEXED_MAX:
            executeSQL(cur, sql)
        else:
            sql += " WHERE tid IN (%s)" % ", ".join(['?'] * len(params))
            executeSQL(cur, sql, params)
        for row in cur:
            if row[0] not in tid2obj:
                continue
            tid2obj[row[0]].end_timestamp    = row[1]
            tid2obj[row[0]].end_rpmdbversion = row[2]
            tid2obj[row[0]].return_code      = row[3]

        # Go through backwards, and see if the rpmdb versions match
        las = None
        for obj in reversed(ret):
            cur_rv = obj.beg_rpmdbversion
            las_rv = None
            if las is not None:
                las_rv = las.end_rpmdbversion
            if las_rv is None or cur_rv is None or (las.tid + 1) != obj.tid:
                pass
            elif las_rv != cur_rv:
                obj.altered_lt_rpmdb = True
                las.altered_gt_rpmdb = True
            else:
                obj.altered_lt_rpmdb = False
                las.altered_gt_rpmdb = False
            las = obj

        return ret

    def last(self):
        """ This is the last full transaction. So any imcomplete transactions
            do not count. """
        cur = self._get_cursor()
        sql =  """SELECT tid,
                         trans_beg.timestamp AS beg_ts,
                         trans_beg.rpmdb_version AS beg_rv,
                         trans_end.timestamp AS end_ts,
                         trans_end.rpmdb_version AS end_rv,
                         loginuid, return_code
                  FROM trans_beg JOIN trans_end USING(tid)
                  ORDER BY beg_ts DESC, tid ASC
                  LIMIT 1"""
        executeSQL(cur, sql)
        for row in cur:
            return YumHistoryTransaction(self, row)
        return None

    def _yieldSQLDataList(self, patterns, fields, ignore_case):
        """Yields all the package data for the given params. """

        cur = self._get_cursor()
        qsql = _FULL_PARSE_QUERY_BEG

        pat_sqls = []
        pat_data = []
        for (pattern, rest) in patterns:
            for field in fields:
                if ignore_case:
                    pat_sqls.append("%s LIKE ?%s" % (field, rest))
                else:
                    pat_sqls.append("%s %s ?" % (field, rest))
                pat_data.append(pattern)
        assert pat_sqls

        qsql += " OR ".join(pat_sqls)
        executeSQL(cur, qsql, pat_data)
        for x in cur:
            yield x

    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        # Search packages ... kind of sucks that it's search not list, pkglist?

        data = _setupHistorySearchSQL(patterns, ignore_case)
        (need_full, patterns, fields, names) = data

        ret = []
        pkgtupids = set()
        for row in self._yieldSQLDataList(patterns, fields, ignore_case):
            pkgtupids.add(row[0])

        cur = self._get_cursor()
        sql =  """SELECT tid FROM trans_data_pkgs WHERE pkgtupid IN """
        sql += "(%s)" % ",".join(['?'] * len(pkgtupids))
        params = list(pkgtupids)
        tids = set()
        if len(params) > yum.constants.PATTERNS_INDEXED_MAX:
            executeSQL(cur, """SELECT tid FROM trans_data_pkgs""")
            for row in cur:
                if row[0] in params:
                    tids.add(row[0])
            return tids
        if not params:
            return tids
        executeSQL(cur, sql, params)
        for row in cur:
            tids.add(row[0])
        return tids

    def _create_db_file(self):
        """ Create a new history DB file, populating tables etc. """

        _db_file = '%s/%s-%s.%s' % (self.conf.db_path,
                                    'history',
                                    time.strftime('%Y-%m-%d'),
                                    'sqlite')
        if self._db_file == _db_file:
            os.rename(_db_file, _db_file + '.old')
        self._db_file = _db_file
                
        cur = self._get_cursor()
        ops = ['''\
 CREATE TABLE trans_beg (
     tid INTEGER PRIMARY KEY,
     timestamp INTEGER NOT NULL, rpmdb_version TEXT NOT NULL,
     loginuid INTEGER);
''', '''\
 CREATE TABLE trans_end (
     tid INTEGER PRIMARY KEY REFERENCES trans_beg,
     timestamp INTEGER NOT NULL, rpmdb_version TEXT NOT NULL,
     return_code INTEGER NOT NULL);
''', '''\
\
 CREATE TABLE trans_with_pkgs (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups);
''', '''\
\
 CREATE TABLE trans_error (
     mid INTEGER PRIMARY KEY,
     tid INTEGER NOT NULL REFERENCES trans_beg,
     msg TEXT NOT NULL);
''', '''\
 CREATE TABLE trans_script_stdout (
     lid INTEGER PRIMARY KEY,
     tid INTEGER NOT NULL REFERENCES trans_beg,
     line TEXT NOT NULL);
''', '''\
\
 CREATE TABLE trans_data_pkgs (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups,
     done BOOL NOT NULL DEFAULT FALSE, state TEXT NOT NULL);
''', '''\
\
 CREATE TABLE pkgtups (
     pkgtupid INTEGER PRIMARY KEY,     name TEXT NOT NULL, arch TEXT NOT NULL,
     epoch TEXT NOT NULL, version TEXT NOT NULL, release TEXT NOT NULL,
     checksum TEXT);
''', '''\
 CREATE INDEX i_pkgtup_naevr ON pkgtups (name, arch, epoch, version, release);
''']
        for op in ops:
            cur.execute(op)
        self._commit()

# Pasted from sqlitesack
_FULL_PARSE_QUERY_BEG = """
SELECT pkgtupid,name,epoch,version,release,arch,
  name || "." || arch AS sql_nameArch,
  name || "-" || version || "-" || release || "." || arch AS sql_nameVerRelArch,
  name || "-" || version AS sql_nameVer,
  name || "-" || version || "-" || release AS sql_nameVerRel,
  epoch || ":" || name || "-" || version || "-" || release || "." || arch AS sql_envra,
  name || "-" || epoch || ":" || version || "-" || release || "." || arch AS sql_nevra
  FROM pkgtups
  WHERE 
"""
