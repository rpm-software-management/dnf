# Copyright (C) 2009, 2012-2017  Red Hat, Inc.
#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# James Antill <james@fedoraproject.org>

import os
import glob
import time
from dnf.yum import misc


class AddonData(object):
    def __init__(self, db_path, root='/'):
        self.conf = misc.GenericHolder()
        self._db_date = time.strftime("%Y-%m-%d")
        if not os.path.normpath(db_path).startswith(root):
            self.conf.db_path = os.path.normpath(root + '/' + db_path)
        else:
            self.conf.db_path = os.path.normpath('/' + db_path)

        self.conf.addon_path = self.conf.db_path + '/' + self._db_date

    def write(self, tid, dataname, data):
        """append data to an arbitrary-named file in the history
           addon_path/transaction id location,
           returns True if write succeeded, False if not"""

        if not dataname:
            return False

        if not data:
            return False

        # make sure the tid dir exists
        tid_dir = self.conf.addon_path + '/' + str(tid)

        if not os.path.exists(tid_dir):
            try:
                os.makedirs(tid_dir, mode=0o700)
            except (IOError, OSError) as e:
                # emit a warning/raise an exception?
                return False

        # cleanup dataname
        safename = dataname.replace('/', '_')
        data_fn = tid_dir + '/' + safename
        try:
            # open file in append
            fo = open(data_fn, 'wb+')
            # write data
            fo.write(data.encode('utf-8'))
            # flush data
            fo.flush()
            fo.close()
        except (IOError, OSError) as e:
            return False
        # return
        return True

    def read(self, tid, item=None):
        hist_and_tid = self.conf.addon_path + '/' + str(tid) + '/'
        addon_info = glob.glob(hist_and_tid + '*')
        addon_names = [i.replace(hist_and_tid, '') for i in addon_info]
        if not item:
            return addon_names
        if item not in addon_names:
            # XXX history needs SOME kind of exception, or warning, I think?
            return None
        fo = open(hist_and_tid + item, 'r')
        data = fo.read()
        fo.close()
        return data
