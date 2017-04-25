# subject.py
# Implements Subject.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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
import re


class Subject(object):
    # :api

    def __init__(self, pkg_spec, ignore_case=False):
        self.subj = hawkey.Subject(pkg_spec)  # internal subject
        self.icase = ignore_case

    def _nevra_to_filters(self, query, nevra):
        nevra_attrs = [("name", True), ("epoch", False),
                       ("version", False), ("release", False),
                       ("arch", False)]

        for (name, add_flags) in nevra_attrs:
            attr = getattr(nevra, name)
            flags = []
            if attr is not None:
                if add_flags:
                    flags = self._query_flags
                query._filterm(*flags, **{name + '__glob': attr})

        return query

    @property
    def _query_flags(self):
        flags = []
        if self.icase:
            flags.append(hawkey.ICASE)
        return flags

    @property
    def _filename_pattern(self):
        return re.search(r"^\*?/", self.subj.pattern)

    @property
    def _pattern(self):
        return self.subj.pattern

    def _is_arch_specified(self, sack):
        for nevra in self.subj.nevra_possibilities():
            if nevra:
                q = self._nevra_to_filters(sack.query(), nevra)
                if q:
                    if nevra.arch:
                        return is_glob_pattern(nevra.arch)
        return False

    def _has_nevra_just_name(self, sack, forms=None):
        kwargs = {}
        if forms is not None:
            kwargs['form'] = forms
        for nevra in self.subj.nevra_possibilities(**kwargs):
            if nevra:
                q = self._nevra_to_filters(sack.query(), nevra)
                if q:
                    return nevra._has_just_name()
        return False

    def get_best_query(self, sack, with_nevra=True, with_provides=True, with_filenames=True,
                       forms=None):
        # :api

        pat = self._pattern
        kwargs = {}
        if with_nevra:
            if forms:
                kwargs['form'] = forms

            for nevra in self.subj.nevra_possibilities(**kwargs):
                if nevra:
                    q = self._nevra_to_filters(sack.query(), nevra)
                    if q:
                        return q

        if not forms:
            if with_provides:
                q = sack.query()._filterm(provides__glob=self._pattern)
                if q:
                    return q

            if with_filenames:
                if self._filename_pattern:
                    return sack.query().filter(file__glob=pat)

        return sack.query().filter(empty=True)

    def get_best_selector(self, sack, forms=None, obsoletes=True):
        # :api

        kwargs = {}
        if forms:
            kwargs['form'] = forms
        sltr = dnf.selector.Selector(sack)
        for nevra in self.subj.nevra_possibilities(**kwargs):
            if nevra:
                q = self._nevra_to_filters(sack.query(), nevra).filter(arch__neq="src")
                if q:
                    if obsoletes and nevra._has_just_name():
                        q = q.union(sack.query().filter(obsoletes=q))
                    return sltr.set(pkg=q)

        if not forms:
            q = sack.query()._filterm(provides__glob=self._pattern)
            if q:
                return sltr.set(pkg=q)

            if self._filename_pattern:
                return sltr.set(pkg=sack.query()._filterm(file__glob=self._pattern))

        return sltr

    def _get_best_selectors(self, sack, forms=None, obsoletes=True):
        if not self._filename_pattern and is_glob_pattern(self._pattern):
            with_obsoletes = False
            if obsoletes and self._has_nevra_just_name(sack, forms=forms):
                with_obsoletes = True
            q = self.get_best_query(sack, forms=forms).filter(arch__neq="src")
            sltrs = []
            for name, pkgs_list in q._name_dict().items():
                sltr = dnf.selector.Selector(sack)
                if with_obsoletes:
                    pkgs_list = pkgs_list + sack.query().filter(
                        obsoletes=pkgs_list).run()
                sltr.set(pkg=pkgs_list)
                sltrs.append(sltr)
            return sltrs

        return [self.get_best_selector(sack, forms, obsoletes)]
