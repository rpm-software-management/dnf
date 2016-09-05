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

"""An extension that ensures that given features are present."""


import sys

import dnf.rpm


if __name__ == '__main__':
    FTR_SPECS = {'hawkey-0.5.3-1.fc21.i686'}  # <-- SET YOUR FEATURES HERE.
    RPM_SPECS = {'./hawkey-0.5.3-1.fc21.i686.rpm'}  # <-- SET YOUR RPMS HERE.
    GRP_SPECS = {'kde-desktop'}  # <-- SET YOUR GROUPS HERE.

    with dnf.Base() as base:
        # Substitutions are needed for correct interpretation of repo files.
        RELEASEVER = dnf.rpm.detect_releasever(base.conf.installroot)
        base.conf.substitutions['releasever'] = RELEASEVER
        # Repositories are needed if we want to install anything.
        base.read_all_repos()
        # A sack is required by marking methods and dependency resolving.
        base.fill_sack()
        # Feature marking methods set the user request.
        for ftr_spec in FTR_SPECS:
            try:
                base.install(ftr_spec)
            except dnf.exceptions.MarkingError:
                sys.exit('Feature(s) cannot be found: ' + ftr_spec)
        # Package marking methods set the user request.
        try:
            base.package_install(base.add_remote_rpms(RPM_SPECS, strict=False))
        except EnvironmentError as e:
            sys.exit(e)
        # Comps data reading initializes the base.comps attribute.
        if GRP_SPECS:
            base.read_comps(arch_filter=True)
        # Group marking methods set the user request.
        for grp_spec in GRP_SPECS:
            group = base.comps.group_by_pattern(grp_spec)
            if not group:
                sys.exit('Group cannot be found: ' + grp_spec)
            base.group_install(group, ['mandatory', 'default'])
        # Resolving finds a transaction that allows the packages installation.
        try:
            base.resolve()
        except dnf.exceptions.DepsolveError:
            sys.exit('Dependencies cannot be resolved.')
        # The packages to be installed must be downloaded first.
        try:
            base.download_packages(base.transaction.install_set)
        except dnf.exceptions.DownloadError:
            sys.exit('Required package cannot be downloaded.')
        # The request can finally be fulfilled.
        base.do_transaction()
