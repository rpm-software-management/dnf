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

.. contents::

=============
 CLI changes
=============

DNF :ref:`History <history_command-label>` info ``--last`` option
=================================================================

``<transaction-spec>`` can be specified by parameter ``--last`` or 
``--last-<offset>`` instead of subcommand ``last`` or ``last-<offset>``,
where ``<offset>`` is a positive integer. It specifies offset-th
transaction preceding the most recent transaction.

Reversion to Yum's configuration directive ``includepkgs`` and ``excludepkgs``
==============================================================================

Due to better compatibility with yum DNF's conf directive ``include`` was
was replaced with origin conf directive :ref:`includepkgs <include-label>`. 
Same for conf directive :ref:`excludepkgs <exclude-label>`.

Option ``--installroot`` documented
===================================

Optional argument \-\ :ref:`-installroot <installroot-label>` is now documented.

==================
Python API changes
==================

Non-API methods and attributes are private
==========================================

.. important::

        All non-API methods and attributes of supported modules are private
        to accomplish more distinguishable API.

DNF group install ``--with-optional`` option
============================================

Installation of optional packages of group is changed from subcommand 
``with-optional`` to parameter ``--with-optional``.

Following API methods accept different arguments
================================================

1. Base.add_remote_rpms(path_list, strict=True)
2. Command.configure()
3. Command.run()
4. Plugin.read_config(conf)
