#!/usr/bin/env python3
# Copyright (C) 2016  Red Hat, Inc.
# Author: Eduard Cuba <xcubae00@stud.fit.vutbr.cz>
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.

import os
import sys
import sqlite3
import glob
import json
from .types import SwdbItem, convert_reason


def CONSTRUCT_NAME(row):
    _NAME = row[1] + '-' + row[3] + '-' + row[4] + '-' + row[5]
    return _NAME


def PACKAGE_DATA_INSERT(cursor, data):
    cursor.execute('INSERT INTO PACKAGE_DATA VALUES (null,?,?,?,?,?,?,?)', data)


def RPM_DATA_INSERT(cursor, data):
    cursor.execute('INSERT INTO RPM_DATA VALUES (null,?,?,?,?,?,?,?,?,?,?,?)', data)


def TRANS_DATA_INSERT(cursor, data):
    cursor.execute('INSERT INTO TRANS_DATA VALUES (null,?,?,?,?,?,?,?)', data)


def TRANS_INSERT(cursor, data):
    cursor.execute('INSERT INTO TRANS VALUES (?,?,?,?,?,?,?,?,?)', data)


# create binding with repo - returns R_ID
def BIND_REPO(cursor, name):
    cursor.execute('SELECT R_ID FROM REPO WHERE name=?', (name, ))
    R_ID = cursor.fetchone()
    if R_ID is None:
        cursor.execute('INSERT INTO REPO VALUES(null,?,0,0)', (name, ))
        cursor.execute('SELECT last_insert_rowid()')
        R_ID = cursor.fetchone()
    return R_ID[0]


# create binding with STATE_TYPE - returns ID
def BIND_STATE(cursor, desc):
    cursor.execute('SELECT state FROM STATE_TYPE WHERE description=?', (desc, ))
    STATE_ID = cursor.fetchone()
    if STATE_ID is None:
        cursor.execute('INSERT INTO STATE_TYPE VALUES(null,?)', (desc, ))
        cursor.execute('SELECT last_insert_rowid()')
        STATE_ID = cursor.fetchone()
    return STATE_ID[0]


# create binding with OUTPUT_TYPE - returns ID
def BIND_OUTPUT(cursor, desc):
    cursor.execute('SELECT type FROM OUTPUT_TYPE WHERE description=?', (desc, ))
    OUTPUT_ID = cursor.fetchone()
    if OUTPUT_ID is None:
        cursor.execute('INSERT INTO OUTPUT_TYPE VALUES(null,?)', (desc, ))
        cursor.execute('SELECT last_insert_rowid()')
        OUTPUT_ID = cursor.fetchone()
    return OUTPUT_ID[0]


# groups packages bindings
def ADD_GROUPS_PACKAGE(cursor, gid, name):
    cursor.execute('INSERT INTO GROUPS_PACKAGE VALUES(null,?,?)', (gid, name))


def ADD_GROUPS_EXCLUDE(cursor, gid, name):
    cursor.execute('INSERT INTO GROUPS_EXCLUDE VALUES(null,?,?)', (gid, name))


# env exclude
def ADD_ENV_EXCLUDE(cursor, eid, name):
    cursor.execute('INSERT INTO ENVIRONMENTS_EXCLUDE VALUES(null,?,?)',
                   (eid, name))


# bind enviroment with groups
def BIND_ENV_GROUP(cursor, eid, name_id):
    cursor.execute('SELECT G_ID FROM GROUPS WHERE name_id=?', (name_id, ))
    tmp_bind_gid = cursor.fetchone()
    if tmp_bind_gid:
        cursor.execute('INSERT INTO ENVIRONMENTS_GROUPS VALUES(null,?,?)',
                       (eid, tmp_bind_gid[0]))


# integrity optimalization
def BIND_PID_PDID(cursor, pid):
    cursor.execute('SELECT PD_ID FROM PACKAGE_DATA WHERE P_ID=?', (pid, ))
    PPD_ID = cursor.fetchone()
    if PPD_ID is None:
        cursor.execute('INSERT INTO PACKAGE_DATA VALUES(null,?,?,?,?,?,?,?)',
                       (pid, '', '', '', '', '', ''))
        cursor.execute('SELECT last_insert_rowid()')
        PPD_ID = cursor.fetchone()
    return PPD_ID[0]


# YUMDB
def GET_YUMDB_PACKAGES(cursor, yumdb_path, PACKAGE_DATA):
    pkglist = {}
    # get package list of yumdb
    for dir in os.listdir(yumdb_path):
        for subdir in os.listdir(os.path.join(yumdb_path, dir)):
            pkglist[subdir.partition('-')[2]] = os.path.join(dir, subdir)

    # fetching aditional values from directory yumdb
    cursor.execute('SELECT * FROM PACKAGE')
    allrows = cursor.fetchall()

    for row in allrows:
        name = CONSTRUCT_NAME(row)
        if name in pkglist:
            record_PD = [None] * len(PACKAGE_DATA)
            path = os.path.join(yumdb_path, pkglist[name])
            tmp_reason = ''
            tmp_releasever = ''
            tmp_cmdline = ''
            for file in os.listdir(path):
                if file in PACKAGE_DATA:
                    with open(os.path.join(path, file)) as f:
                        record_PD[PACKAGE_DATA.index(file)] = f.read()
                elif file == "from_repo":
                    # create binding with REPO table
                    with open(os.path.join(path, file)) as f:
                        record_PD[PACKAGE_DATA.index("R_ID")] = BIND_REPO(
                            cursor,
                            f.read())
                # some additional data
                elif file == "reason":
                    with open(os.path.join(path, file)) as f:
                        tmp_reason = convert_reason(f.read())
                elif file == "releasever":
                    with open(os.path.join(path, file)) as f:
                        tmp_releasever = f.read()
                elif file == "command_line":
                    with open(os.path.join(path, file)) as f:
                        tmp_cmdline = f.read()

            actualPDID = BIND_PID_PDID(cursor, row[0])

            if record_PD[PACKAGE_DATA.index('R_ID')]:
                cursor.execute('UPDATE PACKAGE_DATA SET R_ID=? WHERE PD_ID=?',
                               (record_PD[PACKAGE_DATA.index('R_ID')],
                                actualPDID))

            if record_PD[PACKAGE_DATA.index('from_repo_revision')]:
                cursor.execute('''UPDATE PACKAGE_DATA SET from_repo_revision=?
                               WHERE PD_ID=?''',
                               (record_PD[PACKAGE_DATA.index(
                                          'from_repo_revision')],
                                actualPDID))

            if record_PD[PACKAGE_DATA.index('from_repo_timestamp')]:
                cursor.execute('''UPDATE PACKAGE_DATA SET from_repo_timestamp=?
                               WHERE PD_ID=?''',
                               (record_PD[PACKAGE_DATA.index(
                                          'from_repo_timestamp')],
                                actualPDID))

            if record_PD[PACKAGE_DATA.index('installed_by')]:
                cursor.execute('''UPDATE PACKAGE_DATA SET installed_by=?
                               WHERE PD_ID=?''',
                               (record_PD[PACKAGE_DATA.index('installed_by')],
                                actualPDID))

            if record_PD[PACKAGE_DATA.index('changed_by')]:
                cursor.execute('''UPDATE PACKAGE_DATA SET changed_by=?
                               WHERE PD_ID=?''',
                               (record_PD[PACKAGE_DATA.index('changed_by')],
                                actualPDID))

            if record_PD[PACKAGE_DATA.index('installonly')]:
                cursor.execute('''UPDATE PACKAGE_DATA SET installonly=?
                               WHERE PD_ID=?''',
                               (record_PD[PACKAGE_DATA.index('installonly')],
                                actualPDID))

            # other tables
            if tmp_reason:
                cursor.execute('UPDATE TRANS_DATA SET reason=? WHERE PD_ID=?',
                               (tmp_reason, actualPDID))
            if tmp_releasever:
                cursor.execute('SELECT T_ID FROM TRANS_DATA WHERE PD_ID=?',
                               (actualPDID,))
                tmp_tid = cursor.fetchone()
                if tmp_tid:
                    cursor.execute('''UPDATE TRANS SET releasever=?
                                   WHERE T_ID=?''',
                                   (tmp_releasever, tmp_tid[0]))

            if tmp_cmdline:
                cursor.execute('SELECT T_ID FROM TRANS_DATA WHERE PD_ID=?',
                               (actualPDID,))

                tmp_tid = cursor.fetchone()
                if tmp_tid:
                    cursor.execute('UPDATE TRANS SET cmdline=? WHERE T_ID=?',
                                   (tmp_cmdline, tmp_tid[0]))


def run(input_dir='/var/lib/dnf/', output_file='/var/lib/dnf/history/swdb.sqlite'):
    yumdb_path = os.path.join(input_dir, 'yumdb')
    history_path = os.path.join(input_dir, 'history')
    groups_path = os.path.join(input_dir, 'groups.json')

    # check path to yumdb dir
    if not os.path.isdir(yumdb_path):
        sys.stderr.write('Error: yumdb directory not valid\n')
        return False

    # check path to history dir
    if not os.path.isdir(history_path):
        sys.stderr.write('Error: history directory not valid\n')
        return False

    # check historyDB file and pick newest one
    historydb_file = glob.glob(os.path.join(history_path, "history*"))
    if len(historydb_file) < 1:
        sys.stderr.write('Error: history database file not valid\n')
        return False
    historydb_file.sort()
    historydb_file = historydb_file[0]

    if not os.path.isfile(historydb_file):
        sys.stderr.write('Error: history database file not valid\n')
        return False

    # initialise variables
    task_performed = 0
    task_failed = 0
    try:
        # initialise historyDB
        historyDB = sqlite3.connect(historydb_file)
        h_cursor = historyDB.cursor()
        # initialise output DB
        database = sqlite3.connect(output_file)
        cursor = database.cursor()
    except:
        sys.stderr.write('FAIL: aborting SWDB transformer\n')
        return False

    # value distribution in tables
    PACKAGE_DATA = ['P_ID', 'R_ID', 'from_repo_revision',
                    'from_repo_timestamp', 'installed_by', 'changed_by',
                    'installonly']

    PACKAGE = ['P_ID', 'name', 'epoch', 'version', 'release', 'arch',
               'checksum_data', 'checksum_type', 'type']

    TRANS_DATA = ['T_ID', 'PD_ID', 'TG_ID', 'done', 'ORIGINAL_TD_ID', 'reason',
                  'state']

    TRANS = ['T_ID', 'beg_timestamp', 'end_timestamp', 'beg_RPMDB_version',
             'end_RPMDB_version', 'cmdline', 'loginuid', 'releasever',
             'return_code']

    GROUPS = ['name_id', 'name', 'ui_name', 'installed', 'pkg_types']

    ENVIRONMENTS = ['name_id', 'name', 'ui_name', 'pkg_types', 'grp_types']

    RPM_DATA = ['P_ID', 'buildtime', 'buildhost', 'license', 'packager',
                'size', 'sourcerpm', 'url', 'vendor', 'committer',
                'committime']

    # contruction of PACKAGE from pkgtups
    h_cursor.execute('SELECT * FROM pkgtups')
    for row in h_cursor:
        record_P = [''] * len(PACKAGE)  # init
        record_P[0] = row[0]  # P_ID
        record_P[1] = row[1]  # name
        record_P[2] = row[3]  # epoch
        record_P[3] = row[4]  # version
        record_P[4] = row[5]  # release
        record_P[5] = row[2]  # arch
        if row[6]:
            record_P[6] = row[6].split(":", 2)[1]  # checksum_data
            record_P[7] = row[6].split(":", 2)[0]  # checksum_type
        record_P[8] = SwdbItem.RPM  # type
        cursor.execute('INSERT INTO PACKAGE VALUES (?,?,?,?,?,?,?,?,?)',
                       record_P)

    # save changes
    database.commit()

    # construction of PACKAGE_DATA according to pkg_yumdb
    actualPID = 0
    record_PD = [''] * len(PACKAGE_DATA)
    h_cursor.execute('SELECT * FROM pkg_yumdb')
    # for each row in pkg_yumdb
    for row in h_cursor:
        newPID = row[0]

        if actualPID != newPID:
            if actualPID != 0:
                record_PD[PACKAGE_DATA.index('P_ID')] = actualPID
                # insert new record into PACKAGE_DATA
                PACKAGE_DATA_INSERT(cursor, record_PD)

            actualPID = newPID
            record_PD = [''] * len(PACKAGE_DATA)

        if row[1] in PACKAGE_DATA:
            # collect data for record from pkg_yumdb
            record_PD[PACKAGE_DATA.index(row[1])] = row[2]

        elif row[1] == "from_repo":
            # create binding with REPO table
            record_PD[PACKAGE_DATA.index("R_ID")] = BIND_REPO(cursor, row[2])

    record_PD[PACKAGE_DATA.index('P_ID')] = actualPID
    PACKAGE_DATA_INSERT(cursor, record_PD)  # insert last record

    # integrity optimalization
    cursor.execute('SELECT P_ID FROM PACKAGE')
    tmp_row = cursor.fetchall()
    for row in tmp_row:
        BIND_PID_PDID(cursor, int(row[0]))

    # save changes
    database.commit()

    # construction of RPM_DATA according to pkg_rpmdb
    actualPID = 0
    record_RPM = [''] * len(RPM_DATA)
    h_cursor.execute('SELECT * FROM pkg_rpmdb')

    # for each row in pkg_rpmdb
    for row in h_cursor:
        newPID = row[0]
        if actualPID != newPID:
            if actualPID != 0:
                record_RPM[RPM_DATA.index('P_ID')] = actualPID
                # insert new record into PACKAGE_DATA
                RPM_DATA_INSERT(cursor, record_RPM)
            actualPID = newPID
            record_RPM = [''] * len(RPM_DATA)

        if row[1] in RPM_DATA:
            # collect data for record from pkg_yumdb
            record_RPM[RPM_DATA.index(row[1])] = row[2]
    record_RPM[RPM_DATA.index('P_ID')] = actualPID
    RPM_DATA_INSERT(cursor, record_RPM)  # insert last record

    # save changes
    database.commit()

    # trans_data construction
    h_cursor.execute('SELECT * FROM trans_data_pkgs')

    for row in h_cursor:
        record_TD = [''] * len(TRANS_DATA)
        record_TD[TRANS_DATA.index('T_ID')] = row[0]  # T_ID
        if row[2] == 'TRUE':
            record_TD[TRANS_DATA.index('done')] = 1
        else:
            record_TD[TRANS_DATA.index('done')] = 0

        record_TD[TRANS_DATA.index('state')] = BIND_STATE(cursor, row[3])
        pkgtups_tmp = int(row[1])

        cursor.execute('SELECT PD_ID FROM PACKAGE_DATA WHERE P_ID=?',
                       (pkgtups_tmp,))

        pkgtups_tmp = cursor.fetchone()
        if pkgtups_tmp:
            record_TD[TRANS_DATA.index('PD_ID')] = pkgtups_tmp[0]
        else:
            task_failed += 1
        task_performed += 1
        TRANS_DATA_INSERT(cursor, record_TD)

    # save changes
    database.commit()

    # resolve STATE_TYPE
    cursor.execute('SELECT * FROM STATE_TYPE')
    state_types = cursor.fetchall()
    fsm_state = 0
    obsoleting_t = 0
    update_t = 0
    downgrade_t = 0
    for a in range(len(state_types)):
        if state_types[a][1] == 'Obsoleting':
            obsoleting_t = a + 1
        elif state_types[a][1] == 'Update':
            update_t = a + 1
        elif state_types[a][1] == 'Downgrade':
            downgrade_t = a + 1

    # find ORIGINAL_TD_ID for Obsoleting and upgraded - via FSM
    previous_TD_ID = 0
    cursor.execute('SELECT * FROM TRANS_DATA')
    tmp_row = cursor.fetchall()
    for row in tmp_row:
        if fsm_state == 0:
            if row[7] == obsoleting_t:
                fsm_state = 1
            elif row[7] == update_t:
                fsm_state = 1
            elif row[7] == downgrade_t:
                fsm_state = 1
            previous_TD_ID = row[0]
        elif fsm_state == 1:
            cursor.execute('''UPDATE TRANS_DATA SET ORIGINAL_TD_ID = ?
                           WHERE TD_ID = ?''',
                           (row[0], previous_TD_ID))
            fsm_state = 0

    # save changes
    database.commit()

    # Construction of TRANS
    h_cursor.execute('SELECT * FROM trans_beg')
    for row in h_cursor:
        record_T = [''] * len(TRANS)
        record_T[TRANS.index('T_ID')] = row[0]
        record_T[TRANS.index('beg_timestamp')] = row[1]
        record_T[TRANS.index('beg_RPMDB_version')] = row[2]
        record_T[TRANS.index('loginuid')] = row[3]
        TRANS_INSERT(cursor, record_T)

    h_cursor.execute('SELECT * FROM trans_end')

    for row in h_cursor:
        cursor.execute('''UPDATE TRANS SET end_timestamp=?,end_RPMDB_version=?,
                       return_code=? WHERE T_ID = ?''',
                       (row[1], row[2], row[3], row[0]))

    h_cursor.execute('SELECT * FROM trans_cmdline')
    for row in h_cursor:
        cursor.execute('UPDATE TRANS SET cmdline=? WHERE T_ID = ?',
                       (row[1], row[0]))

    # fetch releasever
    cursor.execute('SELECT T_ID FROM TRANS WHERE releasever=?', ('', ))
    missing = cursor.fetchall()
    for row in missing:
        cursor.execute('SELECT PD_ID FROM TRANS_DATA WHERE T_ID=?', (row[0], ))
        PDID = cursor.fetchall()
        if PDID:
            for actualPDID in PDID:
                cursor.execute('''SELECT P_ID FROM PACKAGE_DATA
                               WHERE PD_ID=? LIMIT 1''',
                               (actualPDID[0], ))
                actualPID = cursor.fetchone()
                if actualPID:
                    h_cursor.execute('''SELECT yumdb_val FROM pkg_yumdb WHERE
                                     pkgtupid=? AND yumdb_key=? LIMIT 1''',
                                     (actualPID[0], 'releasever'))

                    releasever = h_cursor.fetchone()
                    if releasever:
                        cursor.execute('''UPDATE TRANS SET releasever=? WHERE
                                       T_ID=?''',
                                       (releasever[0], row[0]))
                        break

    # fetch reason
    cursor.execute('SELECT TD_ID,PD_ID FROM TRANS_DATA')
    missing = cursor.fetchall()
    for row in missing:
        cursor.execute('SELECT P_ID FROM PACKAGE_DATA WHERE PD_ID=? LIMIT 1',
                       (row[1], ))
        actualPID = cursor.fetchone()

        if actualPID:
            h_cursor.execute('''SELECT yumdb_val FROM pkg_yumdb
                             WHERE pkgtupid=? AND yumdb_key=? LIMIT 1''',
                             (actualPID[0], 'reason'))

            reason = h_cursor.fetchone()
            if reason:
                t_reason = convert_reason(reason[0])
                cursor.execute('UPDATE TRANS_DATA SET reason=? WHERE TD_ID=?',
                               (t_reason, row[0]))

    # contruction of OUTPUT
    h_cursor.execute('SELECT * FROM trans_script_stdout')
    for row in h_cursor:
        cursor.execute('INSERT INTO OUTPUT VALUES (null,?,?,?)',
                       (row[1], row[2], BIND_OUTPUT(cursor, 'stdout')))

    h_cursor.execute('SELECT * FROM trans_error')
    for row in h_cursor:
        cursor.execute('INSERT INTO OUTPUT VALUES (null,?,?,?)',
                       (row[1], row[2], BIND_OUTPUT(cursor, 'stderr')))

    # fetch additional data from yumdb
    GET_YUMDB_PACKAGES(cursor, yumdb_path, PACKAGE_DATA)

    # construction of GROUPS
    if os.path.isfile(groups_path):
        with open(groups_path) as groups_file:
            data = json.load(groups_file)
            for key in data:
                if key == 'GROUPS':
                    for value in data[key]:
                        record_G = [''] * len(GROUPS)
                        record_G[GROUPS.index('name_id')] = value

                        if 'name' in data[key][value]:
                            record_G[GROUPS.index('name')] =\
                                data[key][value]['name']

                        record_G[GROUPS.index('pkg_types')] =\
                            data[key][value]['pkg_types']

                        record_G[GROUPS.index('installed')] = True
                        if 'ui_name' in data[key][value]:
                            record_G[GROUPS.index('ui_name')] =\
                                data[key][value]['ui_name']

                        cursor.execute('''INSERT INTO GROUPS
                                       VALUES (null,?,?,?,?,?)''',
                                       (record_G))
                        cursor.execute('SELECT last_insert_rowid()')
                        tmp_gid = cursor.fetchone()[0]
                        for package in data[key][value]['full_list']:
                            ADD_GROUPS_PACKAGE(cursor, tmp_gid, package)
                        for package in data[key][value]['pkg_exclude']:
                            ADD_GROUPS_EXCLUDE(cursor, tmp_gid, package)
            for key in data:

                if key == 'ENVIRONMENTS':
                    for value in data[key]:
                        record_E = [''] * len(ENVIRONMENTS)
                        record_E[GROUPS.index('name_id')] = value
                        if 'name' in data[key][value]:
                            record_G[GROUPS.index('name')] =\
                                data[key][value]['name']
                        record_E[ENVIRONMENTS.index('grp_types')] =\
                            data[key][value]['grp_types']
                        record_E[ENVIRONMENTS.index('pkg_types')] =\
                            data[key][value]['pkg_types']
                        if 'ui_name' in data[key][value]:
                            record_E[ENVIRONMENTS.index('ui_name')] =\
                                data[key][value]['ui_name']

                        cursor.execute('''INSERT INTO ENVIRONMENTS
                                       VALUES (null,?,?,?,?,?)''',
                                       (record_E))
                        cursor.execute('SELECT last_insert_rowid()')
                        tmp_eid = cursor.fetchone()[0]

                        for package in data[key][value]['full_list']:
                            BIND_ENV_GROUP(cursor, tmp_eid, package)
                        for package in data[key][value]['pkg_exclude']:
                            ADD_ENV_EXCLUDE(cursor, tmp_eid, package)

    # construction of TRANS_GROUP_DATA from GROUPS
    cursor.execute('SELECT * FROM GROUPS')
    tmp_groups = cursor.fetchall()
    for row in tmp_groups:
        tmp_ui_name = ''
        tmp_trans = ''
        if row[3]:
            tmp_ui_name = "%" + row[3] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name, ))
            tmp_trans = cursor.fetchall()
        if not tmp_trans and row[2]:
            tmp_ui_name = "%" + row[2] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name,))
            tmp_trans = cursor.fetchall()
        if not tmp_trans and row[1]:
            tmp_ui_name = "%" + row[1] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name,))
            tmp_trans = cursor.fetchall()
        if tmp_trans:
            for single_trans in tmp_trans:
                tmp_tuple = (single_trans[0], row[0], row[1], row[2], row[3],
                             row[4], row[5])
                cursor.execute('''INSERT INTO TRANS_GROUP_DATA
                               VALUES(null,?,?,?,?,?,?,?)''',
                               tmp_tuple)

    # construction of TRANS_GROUP_DATA from ENVIRONMENTS
    cursor.execute('SELECT * FROM ENVIRONMENTS WHERE ui_name!=?', ('', ))
    tmp_env = cursor.fetchall()
    for row in tmp_env:
        tmp_ui_name = ''
        tmp_trans = ''
        if row[3]:
            tmp_ui_name = "%" + row[3] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name,))
            tmp_trans = cursor.fetchall()
        if not tmp_trans and row[2]:
            tmp_ui_name = "%" + row[2] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name,))
            tmp_trans = cursor.fetchall()
        if not tmp_trans and row[1]:
            tmp_ui_name = "%" + row[1] + "%"
            cursor.execute('SELECT T_ID FROM TRANS WHERE cmdline LIKE ?',
                           (tmp_ui_name,))
            tmp_trans = cursor.fetchall()
        if tmp_trans:
            for single_trans in tmp_trans:
                cursor.execute('''SELECT G_ID FROM ENVIRONMENTS_GROUPS
                               WHERE E_ID = ?''',
                               (row[0],))
                tmp_groups = cursor.fetchall()
                for gid in tmp_groups:
                    cursor.execute('SELECT * FROM GROUPS WHERE G_ID = ?',
                                   (gid[0],))
                    tmp_group_data = cursor.fetchone()
                    tmp_tuple = (single_trans[0], tmp_group_data[0],
                                 tmp_group_data[1], tmp_group_data[2],
                                 tmp_group_data[3], tmp_group_data[4],
                                 tmp_group_data[5])
                    cursor.execute('''INSERT INTO TRANS_GROUP_DATA
                                   VALUES(null,?,?,?,?,?,?,?)''',
                                   tmp_tuple)

    h_cursor.execute('SELECT * FROM trans_with_pkgs')
    for row in h_cursor:
        tid = row[0]
        pid = row[1]
        cursor.execute('INSERT INTO TRANS_WITH VALUES (null,?,?)', (tid, pid))

    # save changes
    database.commit()

    # close connection
    database.close()
    historyDB.close()

    return task_performed > 0
