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
            if attr is not None and attr != '*':
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
        return self.subj.pattern.startswith('/') or self.subj.pattern.startswith('*/')

    @property
    def _pattern(self):
        return self.subj.pattern

    def _is_arch_specified(self, sack):
        for nevra in self.get_nevra_possibilities():
            if nevra:
                q = self._nevra_to_filters(sack.query(), nevra)
                if q:
                    if nevra.arch:
                        return is_glob_pattern(nevra.arch)
        return False

    def get_nevra_possibilities(self, forms=None):
        # :api
        """
        :param forms:
        :return: generator for every possible nevra. Each possible nevra is represented by Class
        NEVRA object (libdnf) that have attributes name, epoch, version, release, arch
        """

        kwargs = {}
        if forms:
            kwargs['form'] = forms
        return self.subj.nevra_possibilities(**kwargs)

    def _get_nevra_solution(self, sack, with_nevra=True, with_provides=True, with_filenames=True,
                            forms=None):
        """
        Try to find first real solution for subject if it is NEVRA
        @param sack:
        @param forms:
        @return: dict with keys nevra and query
        """
        kwargs = {}
        solution = {'nevra': None, 'query': sack.query().filter(empty=True)}
        if with_nevra:
            if forms:
                kwargs['form'] = forms
            for nevra in self.get_nevra_possibilities(forms=forms):
                if nevra:
                    q = self._nevra_to_filters(sack.query(), nevra)
                    if q:
                        solution['nevra'] = nevra
                        solution['query'] = q
                        return solution

        if not forms:
            if with_provides:
                q = sack.query()._filterm(provides__glob=self._pattern)
                if q:
                    solution['query'] = q
                    return solution

            if with_filenames:
                if self._filename_pattern:
                    solution['query'] = sack.query().filter(file__glob=self._pattern)
                    return solution
        return solution

    def get_best_query(self, sack, with_nevra=True, with_provides=True, with_filenames=True,
                       forms=None):
        # :api

        solution = self._get_nevra_solution(sack, with_nevra=with_nevra,
                                            with_provides=with_provides,
                                            with_filenames=with_filenames,
                                            forms=forms)
        return solution['query']

    def get_best_selector(self, sack, forms=None, obsoletes=True):
        # :api

        kwargs = {}
        if forms:
            kwargs['form'] = forms
        sltr = dnf.selector.Selector(sack)
        solution = self._get_nevra_solution(sack, forms=forms)
        if solution['query']:
            q = solution['query']
            q = q.filter(arch__neq="src")
            if obsoletes and solution['nevra'] and solution['nevra']._has_just_name():
                q = q.union(sack.query().filter(obsoletes=q))
            if q:
                return sltr.set(pkg=q)

        return sltr

    def _get_best_selectors(self, sack, forms=None, obsoletes=True):
        if not self._filename_pattern and is_glob_pattern(self._pattern):
            with_obsoletes = False
            solution = self._get_nevra_solution(sack, forms=forms)
            q = solution['query']
            if obsoletes and solution['nevra'] and solution['nevra']._has_just_name():
                with_obsoletes = True
            q = q.filter(arch__neq="src")
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
