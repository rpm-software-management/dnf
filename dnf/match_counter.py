# match_counter.py
# Implements class MatchCounter.
#
# Copyright (C) 2012  Red Hat, Inc.
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

WEIGHTS = {
    'name'		: 7,
    'summary'		: 4,
    'description'	: 2,
    'url'		: 1,
    }

def _canonize_string_set(sset, length):
    """ Ordered sset with empty strings prepended. """
    current = len(sset)
    l = [''] * (length - current) + sorted(sset)
    return l

class MatchCounter(dict):
    """ Map packages to which which of their attributes matched in a search
        against what values.

        The mapping is: ``package -> [(key, needle), ... ]``.
    """
    @staticmethod
    def _eval_matches(matches):
        # how much is each match worth and return their sum:
        weights = map(lambda m: WEIGHTS[m[0]], matches)
        return sum(weights)

    def _key_func(self):
        """ Get the key function used for sorting matches.

            It is not enough to only look at the matches and order them by the
            sum of their weighted hits. In case this number is the same we have
            to ensure that the same matched needles are next to each other in
            the result.
        """
        max_length = self._max_needles()
        def get_key(pkg):
            return (self._eval_matches(self[pkg]),
                    _canonize_string_set(self.matched_needles(pkg), max_length))
        return get_key

    def _max_needles(self):
        return max(map(lambda pkg: len(self.matched_needles(pkg)), self))

    def add(self, pkg, key, needle):
        self.setdefault(pkg, []).append((key, needle))

    def dump(self):
        for pkg in self:
            print '%s\t%s' % (pkg, self[pkg])

    def matched_haystacks(self, pkg):
        return set(map(lambda m: getattr(pkg, m[0]) , self[pkg]))

    def matched_keys(self, pkg):
        return set(map(lambda m: m[0], self[pkg]))

    def matched_needles(self, pkg):
        return set(map(lambda m: m[1], self[pkg]))

    def sorted(self, reverse=False, limit_to=None):
        keys = limit_to if limit_to else self.iterkeys()
        return sorted(keys, key=self._key_func(), reverse=reverse)

    def total(self):
        return reduce(lambda total, pkg: total + len(self[pkg]) ,self, 0)
