..
  Copyright (C) 2014-2018 Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, see
  <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
  incorporated in the source code or documentation are not subject to the GNU
  General Public License and may only be used or replicated with the express
  permission of Red Hat, Inc.

===============
 RPM Interface
===============

.. module:: dnf.rpm

.. function:: detect_releasever(installroot)

  Return the release name of the distribution of the tree rooted at `installroot`. The function uses information from RPMDB found under the tree.

  Returns ``None`` if the information can not be determined (perhaps because the tree has no RPMDB).

.. function:: detect_releasevers(installroot)

  Returns a tuple of the release name, overridden major release, and overridden minor release of the distribution of the tree rooted at `installroot`. The function uses information from RPMDB found under the tree. The major and minor release versions are usually derived from the release version by splitting it on the first ``.``, but distributions can override the derived major and minor versions. It's preferred to use ``detect_releasevers`` over ``detect_releasever``; if you use the latter, you will not be aware of distribution overrides for the major and minor release versions.

  Returns ``(None, None, None)`` if the information can not be determined (perhaps because the tree has no RPMDB).

  If the distribution does not override the release major version, then the second item of the returned tuple will be ``None``. Likewise, if the release minor version is not overridden, the third return value will be ``None``.

.. function:: basearch(arch)

  Return base architecture of the processor based on `arch` type given. E.g. when `arch` i686 is given then the returned value will be i386.
