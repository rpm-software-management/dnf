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

============
 Exceptions
============

.. exception:: dnf.exceptions.Error

  Base class for all DNF Errors.

.. exception:: dnf.exceptions.CompsError

  Used for errors of comps groups like trying to work with group which is not available.

.. exception:: dnf.exceptions.DeprecationWarning

  Used to emit deprecation warnings using Python's :func:`warnings.warning` function.

.. exception:: dnf.exceptions.DepsolveError

  Error during transaction dependency resolving.

.. exception:: dnf.exceptions.DownloadError

  Error during downloading packages from the repositories.

.. exception:: dnf.exceptions.MarkingError

  Error when DNF was unable to find a match for given package / group / module specification.

.. exception:: dnf.exceptions.MarkingErrors

  Categorized errors during processing of the request. The available error categories are ``no_match_pkg_specs`` for missing packages, ``error_pkg_specs`` for broken packages, ``no_match_group_specs`` for missing groups or modules, ``error_group_specs`` for broken groups or modules and ``module_depsolv_errors`` for modular dependency problems.

.. exception:: dnf.exceptions.RepoError

  Error when loading repositories.
