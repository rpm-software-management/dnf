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

=============================================
 Comps, or the Distribution Compose Metadata
=============================================

.. module:: dnf.comps

.. class:: Comps

  An object of this class can merge comps information from arbitrary repositories. It typically is instantiated from :class:`dnf.Base` and covers all the available repositories.

  The ``*_by_pattern`` methods all take a `pattern` and an optional `case_sensitive` parameter. The pattern is matched against names and IDs of objects in the domain (groups, categories, environments), the globbing characters in `pattern` retain their usual expanding meaning. If `case_sensitive` is ``True``, matching is done in a case-sensitive manner.

  .. attribute:: categories

    List of all contained :class:`dnf.comps.Category` objects.

  .. attribute:: environments

    List of all contained :class:`dnf.comps.Environment` objects ordered by `display_order` tag defined in comps.xml file.

  .. attribute:: groups

    List of all contained :class:`dnf.comps.Group` objects ordered by `display_order` tag defined in comps.xml file.

  .. method:: category_by_pattern(pattern, case_sensitive=False)

    Returns a :class:`dnf.comps.Category` object matching `pattern`, or ``None``.

  .. method:: categories_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Category` objects matching `pattern`.

  .. method:: categories_iter

    Return iterator over all contained :class:`dnf.comps.Category` objects.

  .. method:: environment_by_pattern(pattern, case_sensitive=False)

    Return a :class:`dnf.comps.Environment` object matching `pattern`, or ``None``.

  .. method:: environments_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Environment` objects matching `pattern` ordered by `display_order` tag defined in comps.xml file.

  .. attribute:: environments_iter

    Return iterator over all contained :class:`dnf.comps.Environment` objects in order they appear in comps.xml file.

  .. method:: group_by_pattern(pattern, case_sensitive=False)

    Return a :class:`dnf.comps.Group` object matching `pattern`, or ``None``.

  .. method:: groups_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Group` objects matching `pattern` ordered by `display_order` tag defined in comps.xml file.

  .. attribute:: groups_iter

    Return iterator over all contained :class:`dnf.comps.Group` objects in order they appear in comps.xml file.

.. class:: Package

  Represents comps package data.

  .. NOTE::

    Should not be confused with :class:`dnf.package.Package` which represents a package contained in a :class:`~.Sack`. There is no guarantee whether the comps package has a corresponding real sack package, i.e. there can be no package of given name in the sack, one such package, or more than one. For this reason two separate types are introduced.

  .. attribute:: name

    Name of the package.

  .. attribute:: option_type

    The type of inclusion of this particular package in its group. Must be one of the :data:`inclusion types <dnf.comps.CONDITIONAL>`.

.. class:: Category

  .. attribute:: id

    Unique identifier of the category.

  .. attribute:: name

    Name of the category.

  .. attribute:: ui_name

    The name of the category translated to the language given by the current locale.

  .. attribute:: ui_description

    The description of the category translated to the language given by the current locale.

.. class:: Environment

  Has the same set of attributes as :class:`dnf.comps.Category`.

.. class:: Group

  Has the same set of attributes as :class:`dnf.comps.Category`.

  .. method:: packages_iter()

    Return iterator over all :class:`packages <.Package>` belonging in this group.

Following types of inclusions of objects in their parent objects are defined:

.. data:: CONDITIONAL

.. data:: DEFAULT

.. data:: MANDATORY

.. data:: OPTIONAL
