..
  Copyright (C) 2014-2018 Red Hat, Inc.

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

=========
 Package
=========

.. class:: dnf.package.Package

  Represents a unit of software management, typically corresponds to an RPM file.

  .. attribute:: arch

    Architecture of the package (string).

  .. attribute:: baseurl

    Baseurl of the package (string).

  .. attribute:: buildtime

    Seconds since the epoch when the package was built (integer).

  .. attribute:: chksum

    Tuple with package checksum and checksum type or ``None``. The checksum is returned only for
    packages from repository. The checksum is not returned for installed package or packages from
    commandline repository. The checksum represents @pkgid value which links primary metadata with
    other repository metadata files.

  .. attribute:: conflicts

    Packages that the package conflicts with (list of Hawkey.Reldep).

  .. attribute:: debug_name

    The name of the debug-info package (string).

  .. attribute:: description

    The description of the package (string).

  .. attribute:: downloadsize

    The size of rpm package in bytes (integer).

  .. attribute:: epoch

    Epoch of the package (integer).

  .. attribute:: enhances

    Packages that the package enhances (list of Hawkey.Reldep).

  .. attribute:: evr

    EVR (epoch:version-revision) of the package (string).

  .. attribute:: files

    Files the package provides (list of strings).

  .. attribute:: from_repo

    For installed packages returns id of repository from which the package was installed prefixed
    with '@' (if such information is available in the history database). Otherwise returns id of
    repository the package belongs to (@System for installed packages of unknown origin) (string).

  .. attribute:: group

    Group of the package (string).

  .. attribute:: hdr_chksum

    Tuple with package header checksum and checksum type or ``None``. The checksum is returned only for installed packages.

  .. attribute:: hdr_end

    Header end index for the package. Returns 0 for not known (integer).

  .. attribute:: changelogs

    Changelogs for the package (list of dictionaries with "timestamp", "author" and "text" keys).

  .. attribute:: installed

    Returns ``True`` if the package is installed (boolean).

  .. attribute:: installtime

    Seconds since the epoch when the package was installed (integer).

  .. attribute:: installsize

    Space in bytes the package takes on the system after installation (integer).

  .. attribute:: license

    License of the package (string).

  .. attribute:: medianr

    Media number for the package (integer).

  .. attribute:: name

    The name of the package (string).

  .. attribute:: obsoletes

    Packages that are obsoleted by the package (list of Hawkey.Reldep).

  .. attribute:: provides

    Package's provides (list of Hawkey.Reldep).

  .. attribute:: recommends

    Packages that are recommended by the package (list of Hawkey.Reldep).

  .. attribute:: release

    Release of the package (string).

  .. attribute:: reponame

    Id of repository the package was installed from (string).

  .. attribute:: requires

    Package's requirements, combined requires_pre and regular_requires (list of Hawkey.Reldep).

  .. attribute:: requires_pre

    Installed package's %pre, %post, %preun and %postun requirements (list of Hawkey.Reldep).
    For not installed package returns just %pre and $post requirements.

  .. attribute:: regular_requires

    Package's requirements without %pre, %post, %preun and %postun requirements (list of Hawkey.Reldep).

  .. attribute:: prereq_ignoreinst

    Safe to remove requires_pre requirements of an installed package (list of Hawkey.Reldep).

  .. attribute:: rpmdbid

    The rpmdb ID for the package (integer).

  .. attribute:: source_debug_name

    The name of the source debug-info package (string).

  .. attribute:: source_name

    The name of the source package (string).

  .. attribute:: sourcerpm

    Full name of the SRPM used to build this package (string).

  .. attribute:: suggests

    Packages that are suggested by the package (list of Hawkey.Reldep).

  .. attribute:: summary

    Summary for the package (string).

  .. attribute:: supplements

    Packages that the package supplements (list of Hawkey.Reldep).

  .. attribute:: url

    URL for the package (string).

  .. attribute:: version

    Version of the package (string).

  .. method:: remote_location(schemes=('http', 'ftp', 'file', 'https'))

    The location from where the package can be downloaded from (string). If the information is unavailable
    it returns ``None``. ``schemes`` limits result to list of protocols.
