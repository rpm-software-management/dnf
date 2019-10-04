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

###################
 DNF API Reference
###################

.. contents::

==============
 Introduction
==============

The provided Python API to DNF is supposed to mainly allow writing the following two categories of programs:

1. :doc:`plugins <api_plugins>` to DNF which extend functionality of the system's DNF installation.
2. extension applications that embed DNF (by importing its Python modules) to perform specific package management tasks.

Please refer to the :doc:`use_cases` where you can find examples of API usage.

.. NOTE::

  The API consists of exactly those elements described in this document, items not documented here can change release to release. Opening a `bugzilla`_ if certain needed functionality is not exposed is the right thing to do.

============
 Versioning
============

DNF follows the Semantic Versioning as defined at http://semver.org/.

This basically means that if your piece of software depends on e.g. DNF 1.1, the requirement can be specified as ``1.1 <= dnf < 2``. In other words, you can be sure that your software will be API-compatible with any later release of DNF until the next major version is issued. The same applies for the CLI compatibility.

.. _deprecating-label:

Incompatible API changes are subject to our deprecation policy. Deprecated API items (classes, methods, etc.) are designated as such in the :doc:`release_notes`. The first release where support for such items can be dropped entirely must have, relative to the deprecating release, a higher major version number. DNF will log a warning when a deprecated item is used.

===========
 Contents
===========

API Documentation Contents

.. toctree::
  :maxdepth: 2

  api_common
  api_base
  api_exceptions
  api_conf
  api_repos
  api_sack
  api_queries
  api_selector
  api_package
  api_transaction
  api_comps
  api_plugins
  api_callback
  api_rpm
  api_cli
  api_module

Indices:

* :ref:`genindex`
