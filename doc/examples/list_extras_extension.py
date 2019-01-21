# Copyright (C) 2015  Red Hat, Inc.
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

"""An extension that lists installed packages not available
   in any remote repository.
"""

import dnf


if __name__ == '__main__':

    with dnf.Base() as base:
        # Repositories serve as sources of information about packages.
        base.read_all_repos()
        # A sack is needed for querying.
        base.fill_sack()

        # A query matches all packages in sack
        q = base.sack.query()

        # Derived query matches only available packages
        q_avail = q.available()
        # Derived query matches only installed packages
        q_inst = q.installed()

        available = q_avail.run()
        for pkg in q_inst.run():
            if pkg not in available:
                print(str(pkg))
