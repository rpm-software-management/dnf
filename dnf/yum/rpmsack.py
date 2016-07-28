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

from __future__ import absolute_import
from __future__ import unicode_literals
from . import misc
import dnf.pycomp
import glob
import logging
import os
import rpm

logger = logging.getLogger('dnf')

# For returnPackages(patterns=)
flags = {"GT": rpm.RPMSENSE_GREATER,
         "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER,
         "LT": rpm.RPMSENSE_LESS,
         "LE": rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL,
         "EQ": rpm.RPMSENSE_EQUAL,
         None: 0 }

def _open_no_umask(*args):
    """ Annoying people like to set umask's for root, which screws everything
        up for user readable stuff. """
    oumask = os.umask(0o22)
    try:
        ret = open(*args, encoding='utf-8')
    finally:
        os.umask(oumask)

    return ret

def _makedirs_no_umask(*args):
    """ Annoying people like to set umask's for root, which screws everything
        up for user readable stuff. """
    oumask = os.umask(0o22)
    try:
        ret = os.makedirs(*args)
    finally:
        os.umask(oumask)

    return ret

def _iopen(*args):
    """ IOError wrapper BS for open, stupid exceptions. """
    try:
        ret = open(*args, encoding='utf-8')
    except IOError as e:
        return None, e
    return ret, None

def _sanitize(path):
    return path.replace('/', '').replace('~', '')

class AdditionalPkgDB(object):
    """ Accesses additional package data rpmdb is unable to store.

        Previously known as yumdb.
    """
    # dir: <persistdir>/yumdb
    # pkgs stored in name[0]/pkgid-name-ver-rel-arch dirs
    # dirs have files per piece of info we're keeping, e.g. repoid, install
    # reason, status, etc.

    def __init__(self, db_path):
        self.conf = misc.GenericHolder()
        self.conf.db_path = db_path
        self.conf.writable = False

        self._packages = {} # pkgid = dir
        if not os.path.exists(self.conf.db_path):
            try:
                _makedirs_no_umask(self.conf.db_path)
                self.conf.writable = True
            except (IOError, OSError) as e:
                # some sort of useful thing here? A warning?
                pass
        else:
            if os.access(self.conf.db_path, os.W_OK):
                self.conf.writable = True
        self.yumdb_cache = {'attr' : {}}

    def _get_dir_name(self, pkgtup, pkgid):
        if pkgid in self._packages:
            return self._packages[pkgid]
        (n, a, e, v,r) = pkgtup
        n = _sanitize(n)
        str_pkgid = pkgid
        if pkgid is None:
            str_pkgid = '<nopkgid>'
        elif dnf.pycomp.is_py2str_py3bytes(pkgid):
            str_pkgid = pkgid.decode()
        thisdir = '%s/%s/%s-%s-%s-%s-%s' % (self.conf.db_path,
                                            n[0], str_pkgid, n, v, r, a)
        self._packages[pkgid] = thisdir
        return thisdir

    def get_package(self, po=None, pkgtup=None, pkgid=None):
        """Return an RPMDBAdditionalDataPackage Object for this package"""
        if po:
            thisdir = self._get_dir_name(po.pkgtup, po._pkgid)
        elif pkgtup and pkgid:
            thisdir = self._get_dir_name(pkgtup, pkgid)
        else:
            raise ValueError("Missing arguments.")

        return RPMDBAdditionalDataPackage(self.conf, thisdir,
                                          yumdb_cache=self.yumdb_cache)

class RPMDBAdditionalDataPackage(object):

    # We do auto hardlink on these attributes
    _auto_hardlink_attrs = set(['checksum_type', 'reason',
                                'installed_by', 'changed_by',
                                'from_repo', 'from_repo_revision',
                                'from_repo_timestamp', 'releasever',
                                'command_line'])

    def __init__(self, conf, pkgdir, yumdb_cache=None):
        self._conf = conf
        self._mydir = pkgdir

        self._read_cached_data = {}

        #  'from_repo' is the most often requested piece of data, and is often
        # the same for a huge number of packages. So we use hardlinks to share
        # data, and try to optimize for that.
        #  It's useful for other keys too (installed_by/changed_by/reason/etc.)
        # so we make it generic.
        self._yumdb_cache = yumdb_cache

    def _auto_cache(self, attr, value, fn, info=None):
        """ Create caches for the attr. We have a per. object read cache so at
            worst we only have to read a single attr once. Then we expand that
            with (dev, ino) cache, so hardlink data can be read once for
            multiple packages. """
        self._read_cached_data[attr] = value
        if self._yumdb_cache is None:
            return

        nlinks = 1
        if info is not None:
            nlinks = info.st_nlink
        if nlinks <= 1 and attr not in self._auto_hardlink_attrs:
            return

        if value in self._yumdb_cache['attr']:
            sinfo = self._yumdb_cache['attr'][value][1]
            if info is not None and sinfo is not None:
                if (info.st_dev, info.st_ino) == (sinfo.st_dev, sinfo.st_ino):
                    self._yumdb_cache['attr'][value][2].add(fn)
                    self._yumdb_cache[fn] = value
                    return
            if self._yumdb_cache['attr'][value][0] >= nlinks:
                # We already have a better cache file.
                return

        self._yumdb_cache['attr'][value] = (nlinks, info, set([fn]))
        self._yumdb_cache[fn]            = value

    def _unlink_yumdb_cache(self, fn):
        """ Remove old values from the link cache. """
        if fn in self._yumdb_cache:
            ovalue = self._yumdb_cache[fn]
            if ovalue in self._yumdb_cache['attr']:
                self._yumdb_cache['attr'][ovalue][2].discard(fn)
                if not self._yumdb_cache['attr'][ovalue][2]:
                    del self._yumdb_cache['attr'][ovalue]
            del self._yumdb_cache[fn]

    def _link_yumdb_cache(self, fn, value):
        """ If we have a matching yumdb cache, link() to it instead of having
            to open()+write(). """
        if self._yumdb_cache is None:
            return False

        self._unlink_yumdb_cache(fn)

        if value not in self._yumdb_cache['attr']:
            return False

        assert self._yumdb_cache['attr'][value][2]
        try:
            lfn = next(iter(self._yumdb_cache['attr'][value][2]))
            misc.unlink_f(fn + '.tmp')
            os.link(lfn, fn + '.tmp')
            os.rename(fn + '.tmp', fn)
        except:
            return False

        self._yumdb_cache['attr'][value][2].add(fn)
        self._yumdb_cache[fn] = value

        return True

    def _attr2fn(self, attr):
        """ Given an attribute, return the filename. """
        return os.path.normpath(self._mydir + '/' + attr)

    def _write(self, attr, value):
        # check for self._conf.writable before going on?
        if not os.path.exists(self._mydir):
            _makedirs_no_umask(self._mydir)

        attr = _sanitize(attr)
        if attr in self._read_cached_data:
            del self._read_cached_data[attr]
        fn = self._attr2fn(attr)

        if attr.endswith('.tmp'):
            raise AttributeError("Cannot set attribute %s on %s" % (attr, self))

        # Auto hardlink some of the attrs...
        if self._link_yumdb_cache(fn, value):
            return

        # Default write()+rename()... hardlink -c can still help.
        misc.unlink_f(fn + '.tmp')

        fo = _open_no_umask(fn + '.tmp', 'w')
        try:
            dnf.pycomp.write_to_file(fo, value)
        except (OSError, IOError) as e:
            logger.error("Cannot set attribute %s on %s due to:  %s" % (attr, self, e.strerror))

        fo.flush()
        fo.close()
        del fo
        os.rename(fn +  '.tmp', fn) # even works on ext4 now!:o

        self._auto_cache(attr, value, fn)

    def _read(self, attr):
        attr = _sanitize(attr)

        if attr in self._read_cached_data:
            return self._read_cached_data[attr]
        fn = self._attr2fn(attr)

        if attr.endswith('.tmp'):
            raise AttributeError("%s has no attribute %s" % (self, attr))

        info = misc.stat_f(fn, ignore_EACCES=True)
        if info is None:
            raise AttributeError("%s has no attribute %s" % (self, attr))

        if info.st_nlink > 1 and self._yumdb_cache is not None:
            key = (info.st_dev, info.st_ino)
            if key in self._yumdb_cache:
                self._auto_cache(attr, self._yumdb_cache[key], fn, info)
                return self._read_cached_data[attr]

        fo, e = _iopen(fn)
        if fo is None: # This really sucks, don't do that.
            return '<E:%d>' % e.errno
        value = fo.read()
        fo.close()
        del fo

        if info.st_nlink > 1 and self._yumdb_cache is not None:
            self._yumdb_cache[key] = value
        self._auto_cache(attr, value, fn, info)

        return value

    def _delete(self, attr):
        """remove the attribute file"""

        attr = _sanitize(attr)
        fn = self._attr2fn(attr)
        if attr in self._read_cached_data:
            del self._read_cached_data[attr]
        self._unlink_yumdb_cache(fn)
        if os.path.exists(fn):
            try:
                os.unlink(fn)
            except (IOError, OSError) as e:
                logger.error("Cannot delete attribute %s on %s at %s due to: %s" % (attr, self, fn, e.strerror))

    def __getattr__(self, attr):
        return self._read(attr)

    def __setattr__(self, attr, value):
        if not attr.startswith('_'):
            if value is not None:
                self._write(attr, value)
        else:
            object.__setattr__(self, attr, value)

    def __delattr__(self, attr):
        if not attr.startswith('_'):
            self._delete(attr)
        else:
            object.__delattr__(self, attr)

    def __contains__(self, attr):
        #  This is faster than __iter__ and it makes things fail in a much more
        # obvious way in weird FS corruption cases like: BZ 593436
        x = self.get(attr)
        return x is not None

    def __iter__(self, show_hidden=False):
        for item in self._read_cached_data:
            yield item
        for item in glob.glob(self._mydir + '/*'):
            item = item[(len(self._mydir) + 1):]
            if item in self._read_cached_data:
                continue
            if not show_hidden and item.endswith('.tmp'):
                continue
            yield item

    def clean(self):
        # purge out everything
        for item in self.__iter__(show_hidden=True):
            self._delete(item)
        try:
            os.rmdir(self._mydir)
        except OSError:
            pass

    def get(self, attr, default=None):
        """retrieve an add'l data obj"""

        try:
            res = self._read(attr)
        except AttributeError:
            return default
        return res
