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

###################################
 Changes in DNF-2 compared to DNF-1
###################################

=============
 CLI changes
=============

Reintroduction of YUM's configuration options ``includepkgs`` and ``excludepkgs``
===================================================================================

Due to a better compatibility with YUM, configuration options ``include`` and ``exclude``
were replaced by the original options :ref:`includepkgs <include-label>` and
:ref:`excludepkgs <exclude-label>`.

DNF group install ``--with-optional`` option
============================================

Installation of optional packages of group is changed from subcommand
``with-optional`` to option ``--with-optional``.

==================
Python API changes
==================

All non-API methods and attributes are private
==============================================

.. warning:: All non-API methods and attributes of :doc:`documented modules <api>` are now private
             in order to accomplish more distinguishable API.

Following API methods accept different arguments
================================================

#. :meth:`dnf.Base.add_remote_rpms`
#. :meth:`dnf.Base.group_install`
#. :meth:`dnf.cli.Command.configure`
#. :meth:`dnf.cli.Command.run`
#. :meth:`dnf.Plugin.read_config`
