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

import sqlite3
import glob
import json
from .types import SwdbItem, convert_reason
import logging

logger = logging.getLogger('dnf')


def PACKAGE_DATA_INSERT(cursor, data):
    cursor.execute('INSERT INTO PACKAGE_DATA VALUES (null,?,?,?,?,?,?,?)', data)


def RPM_DATA_INSERT(cursor, data):
    cursor.execute('INSERT INTO RPM_DATA VALUES (null,?,?,?,?,?,?,?,?,?,?,?)', data)


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


# YUMDB
def get_yumdb_packages(cursor, yumdb_path, pid_to_pdid, repo_fn):
    """ Insert additional data from yumdb info SWDB """

    # load whole yumdb into dictionary structure
    pkgs = {}
    for path, dirs, files in os.walk(yumdb_path):
        if dirs:
            continue
        nvra = path.split('/')[-1].partition('-')[2]
        yumdata = {}
        for yumfile in files:
            with open(os.path.join(path, yumfile)) as f:
                yumdata[yumfile] = f.read()
        pkgs[nvra] = yumdata

    PDSTRINGS = ['from_repo_timestamp',
                 'from_repo_revision',
                 'changed_by',
                 'installonly',
                 'installed_by']

    # crate PD_ID to T_ID dictionary for further use
    pdid_to_tid = {}
    cursor.execute('SELECT PD_ID, T_ID FROM TRANS_DATA')
    for row in cursor:
        pdid_to_tid[row[0]] = row[1]

    # get all packages from swdb
    cursor.execute('SELECT P_ID, name, version, release, arch FROM PACKAGE')
    allrows = cursor.fetchall()

    # insert data into rows
    for row in allrows:
        name = '-'.join(row[1:])
        if name in pkgs.keys():
            command = []
            vals = pkgs[name]

            # insert data into PACKAGE_DATA table
            for key in PDSTRINGS:
                temp = vals.get(key)
                if temp:
                    command.append("{}='{}'".format(key, temp))

            # get repository
            temp = vals.get('from_repo')
            if temp:
                repo = repo_fn(cursor, temp)
                command.append("R_ID='{}'".format(repo))

            # get PDID of the package
            pdid = pid_to_pdid.get(row[0])

            # Update PACKAGE_DATA row
            if command:
                cmd = "UPDATE PACKAGE_DATA SET {} WHERE PD_ID={}".format(','.join(command), pdid)
                cursor.execute(cmd)

            # resolve reason
            temp = vals.get('reason')
            if temp:
                reason = convert_reason(temp)
                cursor.execute('UPDATE TRANS_DATA SET reason=? WHERE PD_ID=?', (reason, pdid))

            # resolve releasever and command_line
            releasever = vals.get('releasever')
            command_line = vals.get('command_line')
            if releasever or command_line:
                tid = pdid_to_tid.get(pdid)
                # deciding in Python is faster than running both sqlite statements
                if tid:
                    if releasever and command_line:
                        cursor.execute('UPDATE TRANS SET cmdline=?, releasever=? WHERE T_ID=?',
                                       (command_line, releasever, tid))
                    elif releasever:
                        cursor.execute('UPDATE TRANS SET releasever=? WHERE T_ID=?',
                                       (releasever, tid))
                    else:
                        cursor.execute('UPDATE TRANS SET cmdline=? WHERE T_ID=?',
                                       (command_line, tid))


def run(input_dir='/var/lib/dnf/', output_file='/var/lib/dnf/history/swdb.sqlite'):
    yumdb_path = os.path.join(input_dir, 'yumdb')
    history_path = os.path.join(input_dir, 'history')
    groups_path = os.path.join(input_dir, 'groups.json')

    state_dict = {}
    repo_dict = {}

    # create binding with STATE_TYPE - returns ID
    def bind_state(cursor, desc):
        code = state_dict.get(desc)
        if code:
            return code
        cursor.execute('SELECT state FROM STATE_TYPE WHERE description=?', (desc, ))
        state_id = cursor.fetchone()
        if state_id is None:
            cursor.execute('INSERT INTO STATE_TYPE VALUES(null,?)', (desc, ))
            cursor.execute('SELECT last_insert_rowid()')
            state_id = cursor.fetchone()
        state_dict[desc] = state_id[0]
        return state_id[0]

    # create binding with repo - returns R_ID
    def bind_repo(cursor, name):
        code = repo_dict.get(name)
        if code:
            return code
        cursor.execute('SELECT R_ID FROM REPO WHERE name=?', (name, ))
        rid = cursor.fetchone()
        if rid is None:
            cursor.execute('INSERT INTO REPO VALUES(null,?,0,0)', (name, ))
            cursor.execute('SELECT last_insert_rowid()')
            rid = cursor.fetchone()
        repo_dict[name] = rid[0]
        return rid[0]

    # check path to yumdb dir
    if not os.path.isdir(yumdb_path):
        logger.error('Error: yumdb directory not valid')
        return False

    # check path to history dir
    if not os.path.isdir(history_path):
        logger.write('Error: history directory not valid')
        return False

    # check historyDB file and pick newest one
    historydb_file = glob.glob(os.path.join(history_path, "history*"))
    if len(historydb_file) < 1:
        logger.write('Error: history database file not valid')
        return False
    historydb_file.sort()
    historydb_file = historydb_file[0]

    if not os.path.isfile(historydb_file):
        logger.error('Error: history database file not valid')
        return False

    tmp_output_file = output_file + '.transform'
    try:
        # initialise historyDB
        historyDB = sqlite3.connect(historydb_file)
        h_cursor = historyDB.cursor()
    except:
        logger.error("ERROR: unable to open database '{}'".format(historydb_file))
        return False

    try:
        # initialise output DB
        os.rename(output_file, tmp_output_file)
        database = sqlite3.connect(tmp_output_file)
        cursor = database.cursor()
    except:
        logger.error("ERROR: unable to create database '{}'".format(tmp_output_file))
        return False

    # value distribution in tables
    PACKAGE_DATA = ['P_ID', 'R_ID', 'from_repo_revision',
                    'from_repo_timestamp', 'installed_by', 'changed_by',
                    'installonly']

    TRANS_DATA = ['T_ID', 'PD_ID', 'TG_ID', 'done', 'ORIGINAL_TD_ID', 'reason',
                  'state']

    GROUPS = ['name_id', 'name', 'ui_name', 'installed', 'pkg_types']

    ENVIRONMENTS = ['name_id', 'name', 'ui_name', 'pkg_types', 'grp_types']

    RPM_DATA = ['P_ID', 'buildtime', 'buildhost', 'license', 'packager',
                'size', 'sourcerpm', 'url', 'vendor', 'committer',
                'committime']

    logger.info("Transforming database. It may take a while...")

    # contruction of PACKAGE from pkgtups
    h_cursor.execute('SELECT * FROM pkgtups')
    for row in h_cursor:
        record_P = [
            row[0],  # P_ID
            row[1],  # name
            row[3],  # epoch
            row[4],  # version
            row[5],  # release
            row[2]  # arch
        ]
        if row[6]:
            checksum_type, checksum_data = row[6].split(":", 2)
            record_P.append(checksum_data)
            record_P.append(checksum_type)
        else:
            record_P += ['', '']
        record_P.append(SwdbItem.RPM)  # type
        cursor.execute('INSERT INTO PACKAGE VALUES (?,?,?,?,?,?,?,?,?)', record_P)

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
                record_PD[0] = actualPID
                # insert new record into PACKAGE_DATA
                PACKAGE_DATA_INSERT(cursor, record_PD)

            actualPID = newPID
            record_PD = [''] * len(PACKAGE_DATA)

        if row[1] in PACKAGE_DATA:
            # collect data for record from pkg_yumdb
            record_PD[PACKAGE_DATA.index(row[1])] = row[2]

        elif row[1] == "from_repo":
            # create binding with REPO table
            record_PD[1] = bind_repo(cursor, row[2])

    record_PD[0] = actualPID
    PACKAGE_DATA_INSERT(cursor, record_PD)  # insert last record

    # integrity optimalization
    cursor.execute('SELECT P_ID FROM PACKAGE WHERE P_ID NOT IN (SELECT P_ID FROM PACKAGE_DATA)')
    tmp_row = cursor.fetchall()
    for row in tmp_row:
        cursor.execute("INSERT INTO PACKAGE_DATA VALUES(null,?,'','','','','','')", (row[0],))

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
                record_RPM[0] = actualPID
                # insert new record into PACKAGE_DATA
                RPM_DATA_INSERT(cursor, record_RPM)
            actualPID = newPID
            record_RPM = [''] * len(RPM_DATA)

        if row[1] in RPM_DATA:
            # collect data for record from pkg_yumdb
            record_RPM[RPM_DATA.index(row[1])] = row[2]
    record_RPM[0] = actualPID
    RPM_DATA_INSERT(cursor, record_RPM)  # insert last record

    # save changes
    database.commit()

    # prepare pid to pdid dictionary
    cursor.execute("SELECT PD_ID, P_ID FROM PACKAGE_DATA")
    pid_to_pdid = {}
    for row in cursor:
        pid_to_pdid[row[1]] = row[0]

    # trans_data construction
    h_cursor.execute('SELECT tid, pkgtupid, done, state FROM trans_data_pkgs')
    for row in h_cursor:
        data = [''] * len(TRANS_DATA)
        data[TRANS_DATA.index('done')] = 1 if row[2] == 'TRUE' else 0
        data[TRANS_DATA.index('state')] = bind_state(cursor, row[3])
        data[TRANS_DATA.index('PD_ID')] = pid_to_pdid.get(int(row[1]), 0)
        data[0] = row[0]
        cursor.execute('INSERT INTO TRANS_DATA VALUES (null,?,?,?,?,?,?,?)', data)

    # save changes
    database.commit()

    # resolve STATE_TYPE
    cursor.execute('SELECT * FROM STATE_TYPE')
    state_types = cursor.fetchall()
    fsm_state = 0
    obsoleting_t = 0
    update_t = 0
    downgrade_t = 0
    # get state enum
    for i, item in enumerate(state_types):
        if item[1] == 'Obsoleting':
            obsoleting_t = i + 1
        elif item[1] == 'Update':
            update_t = i + 1
        elif item[1] == 'Downgrade':
            downgrade_t = i + 1

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
            cursor.execute("""UPDATE TRANS_DATA SET ORIGINAL_TD_ID = ?
                           WHERE TD_ID = ?""", (row[0], previous_TD_ID))
            fsm_state = 0

    # save changes
    database.commit()

    trans_cmd = """SELECT tid, trans_beg.timestamp, trans_end.timestamp, trans_beg.rpmdb_version,
                trans_end.rpmdb_version, cmdline, loginuid, null, return_code
                FROM trans_beg join trans_end using(tid) join trans_cmdline using(tid)"""

    # Construction of TRANS
    h_cursor.execute(trans_cmd)
    for row in h_cursor:
        cursor.execute('INSERT INTO TRANS VALUES (?,?,?,?,?,?,?,?,?)', row)

    # get releasever for transactions
    cursor.execute('SELECT T_ID FROM TRANS WHERE releasever=?', ('', ))
    missing = cursor.fetchall()
    for row in missing:
        tid = row[0]
        cmd = "SELECT P_ID FROM TRANS_DATA join PACKAGE_DATA using (PD_ID) WHERE T_ID=? LIMIT 1"
        cursor.execute(cmd)
        pids = cursor.fetchall()
        for pid in pids:
            h_cursor.execute("""SELECT yumdb_val FROM pkg_yumdb WHERE pkgtupid=? AND
                             yumdb_key='releasever' LIMIT 1""", (pid,))
            rlsver = h_cursor.fetchone()
            if rlsver:
                cursor.execute("UPDATE TRANS SET releasever=? WHERE T_ID=?", (rlsver[0], tid))
                break

    # collect reasons
    cursor.execute("""SELECT TD_ID, P_ID FROM TRANS_DATA join PACKAGE_DATA using(PD_ID)
                   join PACKAGE using(P_ID)""")
    missing = cursor.fetchall()
    for row in missing:
        h_cursor.execute("""SELECT yumdb_val FROM pkg_yumdb WHERE pkgtupid=? AND yumdb_key='reason'
                         LIMIT 1""", (row[1],))
        reason = h_cursor.fetchone()
        if reason:
            t_reason = convert_reason(reason[0])
            cursor.execute('UPDATE TRANS_DATA SET reason=? WHERE TD_ID=?', (t_reason, row[0]))

    # fetch additional data from yumdb
    get_yumdb_packages(cursor, yumdb_path, pid_to_pdid, bind_repo)

    # contruction of OUTPUT
    h_cursor.execute('SELECT * FROM trans_script_stdout')
    for row in h_cursor:
        cursor.execute('INSERT INTO OUTPUT VALUES (null,?,?,?)',
                       (row[1], row[2], BIND_OUTPUT(cursor, 'stdout')))

    h_cursor.execute('SELECT * FROM trans_error')
    for row in h_cursor:
        cursor.execute('INSERT INTO OUTPUT VALUES (null,?,?,?)',
                       (row[1], row[2], BIND_OUTPUT(cursor, 'stderr')))

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
                            record_G[GROUPS.index('name')] = data[key][value]['name']

                        record_G[GROUPS.index('pkg_types')] = data[key][value]['pkg_types']

                        record_G[GROUPS.index('installed')] = True
                        if 'ui_name' in data[key][value]:
                            record_G[GROUPS.index('ui_name')] = data[key][value]['ui_name']

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
                            record_G[GROUPS.index('name')] = data[key][value]['name']
                        record_E[ENVIRONMENTS.index('grp_types')] = data[key][value]['grp_types']
                        record_E[ENVIRONMENTS.index('pkg_types')] = data[key][value]['pkg_types']
                        if 'ui_name' in data[key][value]:
                            record_E[ENVIRONMENTS.index('ui_name')] = data[key][value]['ui_name']

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
        command = []
        for pattern in row[1:4]:
            if pattern:
                command.append("cmdline LIKE '%{}%'".format(pattern))
        if command:
            cursor.execute("SELECT T_ID FROM TRANS WHERE " + " or ".join(command))
            tmp_trans = cursor.fetchall()
            if tmp_trans:
                for single_trans in tmp_trans:
                    data = (single_trans[0], row[0], row[1], row[2], row[3], row[4], row[5])
                    cursor.execute("INSERT INTO TRANS_GROUP_DATA VALUES(null,?,?,?,?,?,?,?)", data)

    # construction of TRANS_GROUP_DATA from ENVIRONMENTS
    cursor.execute('SELECT * FROM ENVIRONMENTS WHERE ui_name!=?', ('', ))
    tmp_env = cursor.fetchall()
    for row in tmp_env:
        command = []
        for pattern in row[1:4]:
            if pattern:
                command.append("cmdline LIKE '%{}%'".format(pattern))
        if command:
            cursor.execute("SELECT T_ID FROM TRANS WHERE " + " or ".join(command))
            tmp_trans = cursor.fetchall()
            if tmp_trans:
                for trans in tmp_trans:
                    cursor.execute("SELECT G_ID FROM ENVIRONMENTS_GROUPS WHERE E_ID=?", (row[0],))
                    tmp_groups = cursor.fetchall()
                    for gid in tmp_groups:
                        cursor.execute("SELECT * FROM GROUPS WHERE G_ID=?", (gid[0],))
                        data = cursor.fetchone()
                        tgdata = (trans[0], data[0], data[1], data[2], data[3], data[4], data[5])
                        cursor.execute("INSERT INTO TRANS_GROUP_DATA VALUES(null,?,?,?,?,?,?,?)",
                                       tgdata)

    # create Transaction performed with package
    h_cursor.execute('SELECT tid, pkgtupid FROM trans_with_pkgs')
    for row in h_cursor:
        cursor.execute('INSERT INTO TRANS_WITH VALUES (null,?,?)', row)

    # save changes
    database.commit()

    # close connection
    database.close()
    historyDB.close()

    # successful
    os.rename(tmp_output_file, output_file)

    return True
