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

import rpm
import types
import warnings
import glob
import os
import os.path

from dnf.rpmUtils import miscutils
from dnf.rpmUtils import arch
from dnf.rpmUtils.transaction import initReadOnlyTransaction
import misc
import Errors
from packages import YumInstalledPackage, parsePackages
from packageSack import PackageSackBase, PackageSackVersion

# For returnPackages(patterns=)
import fnmatch
import re

from i18n import to_unicode, _
import constants

flags = {"GT": rpm.RPMSENSE_GREATER,
         "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER,
         "LT": rpm.RPMSENSE_LESS,
         "LE": rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL,
         "EQ": rpm.RPMSENSE_EQUAL,
         None: 0 }

def _open_no_umask(*args):
    """ Annoying people like to set umask's for root, which screws everything
        up for user readable stuff. """
    oumask = os.umask(022)
    try:
        ret = open(*args)
    finally:
        os.umask(oumask)

    return ret

def _makedirs_no_umask(*args):
    """ Annoying people like to set umask's for root, which screws everything
        up for user readable stuff. """
    oumask = os.umask(022)
    try:
        ret = os.makedirs(*args)
    finally:
        os.umask(oumask)

    return ret

def _iopen(*args):
    """ IOError wrapper BS for open, stupid exceptions. """
    try:
        ret = open(*args)
    except IOError, e:
        return None, e
    return ret, None


class RPMInstalledPackage(YumInstalledPackage):

    def __init__(self, rpmhdr, index, rpmdb):
        self._has_hdr = True
        YumInstalledPackage.__init__(self, rpmhdr, yumdb=rpmdb.yumdb)

        self.idx   = index
        self.rpmdb = rpmdb

        self._has_hdr = False
        del self.hdr

    def _get_hdr(self):
        # Note that we can't use hasattr(self, 'hdr') or we'll recurse
        if self._has_hdr:
            return self.hdr

        ts = self.rpmdb.readOnlyTS()
        mi = ts.dbMatch(0, self.idx)
        try:
            return mi.next()
        except StopIteration:
            raise Errors.PackageSackError, 'Rpmdb changed underneath us'

    def __getattr__(self, varname):
        # If these existed, then we wouldn't get here...
        # Prevent access of __foo__, _cached_foo etc from loading the header
        if varname.startswith('_'):
            raise AttributeError, "%s has no attribute %s" % (self, varname)

        if varname != 'hdr': # Don't cache the hdr, unless explicitly requested
            #  Note that we don't even cache the .blah value, but looking up the
            # header is _really_ fast so it's not obvious any of it is worth it.
            # This is different to prco etc. data, which is loaded separately.
            val = self._get_hdr()
        else:
            self.hdr = val = self._get_hdr()
            self._has_hdr = True
        if varname != 'hdr':   #  This is unusual, for anything that happens
            val = val[varname] # a lot we should preload at __init__.
                               # Also note that pkg.no_value raises KeyError.

        return val

    def requiring_packages(self):
        """return list of installed pkgs requiring this package"""
        pkgset = set()
        for (reqn, reqf, reqevr) in self.provides:
            for pkg in self.rpmdb.getRequires(reqn,reqf,reqevr):
                if pkg != self:
                    pkgset.add(pkg)

        for fn in self.filelist + self.dirlist:
            for pkg in self.rpmdb.getRequires(fn, None, (None, None, None)):
                if pkg != self:
                    pkgset.add(pkg)

        return list(pkgset)


    def required_packages(self):
        pkgset = set()
        for (reqn, reqf, reqevr) in self.requires:
            for pkg in self.rpmdb.getProvides(reqn, reqf, reqevr):
                if pkg != self:
                    pkgset.add(pkg)

        return list(pkgset)

class RPMDBProblem:
    '''
    Represents a problem in the rpmdb, from the check_*() functions.
    '''
    def __init__(self, pkg, problem, **kwargs):
        self.pkg = pkg
        self.problem = problem
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])

    def __cmp__(self, other):
        if other is None:
            return 1
        return cmp(self.pkg, other.pkg) or cmp(self.problem, other.problem)


class RPMDBProblemDependency(RPMDBProblem):
    def __str__(self):
        if self.problem == 'requires':
            return "%s %s %s" % (self.pkg, _('has missing requires of'),
                                 self.missing)

        return "%s %s %s: %s" % (self.pkg, _('has installed conflicts'),
                                 self.found,', '.join(map(str, self.conflicts)))


class RPMDBProblemDuplicate(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "duplicate", **kwargs)

    def __str__(self):
        return _("%s is a duplicate with %s") % (self.pkg, self.duplicate)


class RPMDBProblemObsoleted(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "obsoleted", **kwargs)

    def __str__(self):
        return _("%s is obsoleted by %s") % (self.pkg, self.obsoleter)


class RPMDBProblemProvides(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "provides", **kwargs)

    def __str__(self):
        return _("%s provides %s but it cannot be found") % (self.pkg,
                                                             self.provide)

def _sanitize(path):
    return path.replace('/', '').replace('~', '')

class RPMDBAdditionalData(object):
    """class for access to the additional data not able to be stored in the
       rpmdb"""
    # dir: /var/lib/yum/yumdb/
    # pkgs stored in name[0]/name[1]/pkgid-name-ver-rel-arch dirs
    # dirs have files per piece of info we're keeping
    #    repoid, install reason, status, blah, (group installed for?), notes?

    def __init__(self, db_path='/var/lib/yum/yumdb', version_path=None):
        self.conf = misc.GenericHolder()
        self.conf.db_path = db_path
        self.conf.version_path = version_path
        self.conf.writable = False

        self._packages = {} # pkgid = dir
        if not os.path.exists(self.conf.db_path):
            try:
                _makedirs_no_umask(self.conf.db_path)
                self.conf.writable = True
            except (IOError, OSError), e:
                # some sort of useful thing here? A warning?
                pass
        else:
            if os.access(self.conf.db_path, os.W_OK):
                self.conf.writable = True
        #  Don't call _load_all_package_paths to preload, as it's expensive
        # if the dirs. aren't in cache.
        self.yumdb_cache = {'attr' : {}}

    def _load_all_package_paths(self):
        # glob the path and get a dict of pkgs to their subdir
        glb = '%s/*/*/' % self.conf.db_path
        pkgdirs = glob.glob(glb)
        for d in pkgdirs:
            pkgid = os.path.basename(d).split('-')[0]
            self._packages[pkgid] = d

    def _get_dir_name(self, pkgtup, pkgid):
        if pkgid in self._packages:
            return self._packages[pkgid]
        (n, a, e, v,r) = pkgtup
        n = _sanitize(n) # Please die in a fire rpmbuild
        thisdir = '%s/%s/%s-%s-%s-%s-%s' % (self.conf.db_path,
                                            n[0], pkgid, n, v, r, a)
        self._packages[pkgid] = thisdir
        return thisdir

    def get_package(self, po=None, pkgtup=None, pkgid=None):
        """Return an RPMDBAdditionalDataPackage Object for this package"""
        if po:
            thisdir = self._get_dir_name(po.pkgtup, po.pkgid)
        elif pkgtup and pkgid:
            thisdir = self._get_dir_name(pkgtup, pkgid)
        else:
            raise ValueError,"Pass something to RPMDBAdditionalData.get_package"

        return RPMDBAdditionalDataPackage(self.conf, thisdir,
                                          yumdb_cache=self.yumdb_cache)

    def sync_with_rpmdb(self, rpmdbobj):
        """populate out the dirs and remove all the items no longer in the rpmd
           and/or populate various bits to the currently installed version"""
        # TODO:
        # get list of all items in the yumdb
        # remove any no longer in the rpmdb/andor migrate them up to the currently
        # installed version
        # add entries for items in the rpmdb if they don't exist in the yumdb

        pass

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
            lfn = iter(self._yumdb_cache['attr'][value][2]).next()
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
            raise AttributeError, "Cannot set attribute %s on %s" % (attr, self)

        # Auto hardlink some of the attrs...
        if self._link_yumdb_cache(fn, value):
            return

        # Default write()+rename()... hardlink -c can still help.
        misc.unlink_f(fn + '.tmp')

        fo = _open_no_umask(fn + '.tmp', 'w')
        try:
            fo.write(value)
        except (OSError, IOError), e:
            raise AttributeError, "Cannot set attribute %s on %s" % (attr, self)

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
            raise AttributeError, "%s has no attribute %s" % (self, attr)

        info = misc.stat_f(fn, ignore_EACCES=True)
        if info is None:
            raise AttributeError, "%s has no attribute %s" % (self, attr)

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
            except (IOError, OSError):
                raise AttributeError, "Cannot delete attribute %s on %s " % (attr, self)

    def __getattr__(self, attr):
        return self._read(attr)

    def __setattr__(self, attr, value):
        if not attr.startswith('_'):
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
