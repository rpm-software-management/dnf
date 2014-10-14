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
from __future__ import unicode_literals
from dnf.util import first, is_glob_pattern

import dnf.selector
import hawkey

class Subject(object):
    # :api

    def __init__(self, pkg_spec, ignore_case=False):
        self.subj = hawkey.Subject(pkg_spec) # internal subject
        self.icase = ignore_case

    def _nevra_to_filters(self, query, nevra):
        nevra_attrs = [("name", True, True), ("epoch", False, False),
                       ("version", True, False), ("release", False, False),
                       ("arch", True, False)]

        for (name, check_glob, add_flags) in nevra_attrs:
            attr = getattr(nevra, name)
            flags = []
            if attr:
                if add_flags:
                    flags = self._query_flags
                if check_glob:
                    query = query.filter_autoglob(*flags, **{name: attr})
                else:
                    query.filterm(*flags, **{name: attr})

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
    def filename_pattern(self):
        return self.subj.pattern.find('/') != -1

    @property
    def pattern(self):
        return self.subj.pattern

    def is_arch_specified(self, sack):
        nevra = first(self.subj.nevra_possibilities_real(sack, allow_globs=True))
        if nevra and nevra.arch:
            return is_glob_pattern(nevra.arch)
        return False

    def get_greedy_query(self, sack):
        pkgs = set()
        for nevra in self.subj.nevra_possibilities_real(sack, allow_globs=True,
                                                        icase=self.icase):
            q = self._nevra_to_filters(sack.query(), nevra)
            pkgs |= set(q.run())

        for rd in self.subj.reldep_possibilities_real(sack, icase=self.icase):
            q = sack.query().filter(provides=rd)
            pkgs |= set(q.run())

        q = sack.query().filter(*self._query_flags,
                                nevra__glob=self.subj.pattern)
        pkgs |= set(q.run())

        return sack.query().filter(pkg=pkgs)

    def get_best_query(self, sack, with_provides=True, forms=None):
        # :api
        pat = self.subj.pattern
        if self.filename_pattern:
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
        # :api
        sltr = dnf.selector.Selector(sack)
        kwargs = {'allow_globs': True}
        if self.filename_pattern:
            key = "file__glob" if is_glob_pattern(self.pattern) else "file"
            return sltr.set(**{key: self.pattern})
        if forms:
            kwargs['form'] = forms
        nevra = first(self.subj.nevra_possibilities_real(sack, **kwargs))
        if nevra:
            return self._nevra_to_selector(sltr, nevra)

        reldep = first(self.subj.reldep_possibilities_real(sack))
        if reldep:
            dep = str(reldep)
            return sltr.set(provides=dep)
        if is_glob_pattern(self.pattern):
            key = "provides__glob"
            return sltr.set(**{key: self.pattern})
        
        return sltr
