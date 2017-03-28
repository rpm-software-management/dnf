..
  Copyright (C) 2014-2016 Red Hat, Inc.

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

  .. attribute:: buildtime

    Seconds since the epoch when the package was built (integer).

  .. attribute:: debug_name

    The name of the gebug-info package (string).

  .. attribute:: downloadsize

    The size of rpm package in bytes (integer).

  .. attribute:: epoch

    Epoch of the package (integer)

  .. attribute:: files

    Files the package provides (list of strings)

  .. attribute:: installtime

    Seconds since the epoch when the package was installed (integer).

  .. attribute:: installsize

    Space in bytes the package takes on the system after installation (integer).

  .. method:: remote_location(schemes=('http', 'ftp', 'file', 'https'))

    The location from where the package can be downloaded from (string). If information unavailable
    it returns ``None``. ``schemes`` limits result to list of protocols.

  .. attribute:: name

    The name of the package (string).

  .. attribute:: obsoletes

    Packages that are obsoleted by the package (list of Hawkey.Reldep).

  .. attribute:: provides

    Package's provides (list of Hawkey.Reldep).

  .. attribute:: release

    Release of the package (string).

  .. attribute:: requires

    Package's requirements (list of Hawkey.Reldep).

  .. attribute:: source_debug_name

    The name of the source gebug-info package (string).

  .. attribute:: source_name

    The name of the source package (string).

  .. attribute:: sourcerpm

    Full name of the SRPM used to build this package (string).

  .. attribute:: version

    Version of the package (string).
