..
  Copyright (C) 2019 Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, write to the
  Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
  02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
  source code or documentation are not subject to the GNU General Public
  License and may only be used or replicated with the express permission of
  Red Hat, Inc.


############
 Modularity
############

Modularity is new way of building, organizing and delivering packages.
For more details see: https://docs.pagure.org/modularity/


=============
 Definitions
=============

modulemd
    Every repository can contain ``modules`` metadata with modulemd documents.
    These documents hold metadata about modules such as ``Name``, ``Stream`` or list of packages.

(non-modular) package
    Package that doesn't belong to a module.

modular package
    Package that belongs to a module. It is listed in modulemd under the ``artifacts`` section.
    Modular packages can be also identified by having ``%{modularitylabel}`` RPM header set.

(module) stream
    Stream is a collection of packages, a virtual repository. It is identified with
    ``Name`` and ``Stream`` from modulemd separated with colon, for example "postgresql:9.6".


===================
 Package filtering
===================
Without modules, packages with the highest version are used by default.

Module streams can distribute packages with lower versions than available in the
repositories available to the operating system. To make such packages available
for installs and upgrades, the non-modular packages are filtered out when they match
by name with modular packages from any existing stream.


=====================
 Hotfix repositories
=====================
In special cases, a user wants to cherry-pick individual packages provided outside module
streams and make them available on along with packages from the active streams.
Under normal circumstances, such packages are filtered out.
To make the system use packages from a repository regardless of their modularity,
specify ``module_hotfixes=true`` in the .repo file. This protects the repository from package filtering.

Please note the hotfix packages do not override module packages, they only become
part of available package set. It's the package ``Epoch``, ``Version`` and ``Release``
what determines if the package is the latest.


======================
 Fail-safe mechanisms
======================


Repositories with module metadata are unavailable
=================================================
When a repository with module metadata is unavailable, package filtering must keep working.
Non-modular RPMs must remain unavailable and must never get on the system.

This happens when:

* user disables a repository via ``--disablerepo`` or uses ``--repoid``
* user removes a .repo file from disk
* repository is not available and has ``skip_if_unavailable=true``

DNF keeps copies of the latest modulemd for every active stream
and uses them if there's no modulemd available for the stream.
This keeps package filtering working correctly.

The copies are made any time a transaction is resolved and started.
That includes RPM transactions as well as any ``dnf module <enable|disable|reset>`` operations.

When the fail-safe data is used, dnf show such modules as part of @modulefailsafe repository.


Orphaned modular packages
=========================
All packages that are built as a part of a module have ``%{modularitylabel}`` RPM header set.
If such package becomes part of RPM transaction and cannot be associated with any available
modulemd, DNF logs the issue as critical problem.
