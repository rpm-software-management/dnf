# subject.py
# Implements Subject.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
#
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
#

from __future__ import absolute_import
from __future__ import print_function
from dnf.util import first, is_glob_pattern

import dnf.selector
import hawkey

class Subject(object):
    # :api

    def __init__(self, pkg_spec, ignore_case=False):
        self.subj = hawkey.Subject(pkg_spec) # internal subject
        self.icase = ignore_case

    def _nevra_to_filters(self, query, nevra):
        if nevra.name is not None:
            if is_glob_pattern(nevra.name):
                query.filterm(*self._query_flags, name__glob=nevra.name)
            else:
                query.filterm(*self._query_flags, name=nevra.name)
        if nevra.arch is not None:
            query.filterm(arch=nevra.arch)
        if nevra.epoch is not None:
            query.filterm(epoch=nevra.epoch)
        if nevra.version is not None:
            version = nevra.version
            if is_glob_pattern(version):
                query.filterm(version__glob=version)
            else:
                query.filterm(version=version)
        if nevra.release is not None:
            query.filterm(release=nevra.release)
        return query

    @staticmethod
    def _nevra_to_selector(sltr, nevra):
        if nevra.name is not None:
            sltr.set_autoglob(name=nevra.name)
        if nevra.version is not None:
            evr = nevra.version
            if nevra.epoch is not None and nevra.epoch > 0:
                evr = "%d:%s" % (nevra.epoch, evr)
            if nevra.release is None:
                sltr.set(version=evr)
            else:
                evr = "%s-%s" % (evr, nevra.release)
                sltr.set(evr=evr)
        if nevra.arch is not None:
            sltr.set(arch=nevra.arch)
        return sltr

    @property
    def _query_flags(self):
        flags = []
        if self.icase:
            flags.append(hawkey.ICASE)
        return flags

    @property
    def pattern(self):
        return self.subj.pattern

    def get_best_query(self, sack, with_provides=True, forms=None):
        pat = self.subj.pattern
        if pat.startswith('/'):
            return sack.query().filter_autoglob(file=pat)

        kwargs = {'allow_globs' : True,
                  'icase'	: self.icase}
        if forms:
            kwargs['form'] = forms
        nevra = first(self.subj.nevra_possibilities_real(sack, **kwargs))
        if nevra:
            return self._nevra_to_filters(sack.query(), nevra)

        if with_provides:
            reldeps = self.subj.reldep_possibilities_real(sack, icase=self.icase)
            reldep = first(reldeps)
            if reldep:
                return sack.query().filter(provides=reldep)
        return sack.query().filter(empty=True)

    def get_best_selector(self, sack, forms=None):
        kwargs = {'allow_globs' : True}
        if forms:
            kwargs['form'] = forms
        nevra = first(self.subj.nevra_possibilities_real(sack, **kwargs))
        if nevra:
            return self._nevra_to_selector(dnf.selector.Selector(sack), nevra)

        reldep = first(self.subj.reldep_possibilities_real(sack))
        if reldep:
             # we can not handle full Reldeps
            dep = str(reldep)
            assert(not (set(dep) & set("<=>")))
            return dnf.selector.Selector(sack).set(provides=str(reldep))
        return None
