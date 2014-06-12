..
  Copyright (C) 2014  Red Hat, Inc.

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

.. NOTE::

  The API consists of exactly those elements described in this document, items not documented here can change release to release. Opening a `bugzilla`_ if certain needed functionality is not exposed is the right thing to do.

.. _deprecating-label:

====================
 Deprecation Policy
====================

.. WARNING::

  The DNF project has not fully stabilized yet and it is possible parts the API described in this document can change. All such changes are documented per-version in the release notes and are subject to our deprecation policy. We do our best to reduce their number to a necessary minimum.

Depracated API items (classes, methods, etc.) are designated as such in the :doc:`release_notes`. The first release where support for such items can be dropped entirely must be issued at least three months after the issue of the release that announced the deprecation and at the same time have, relatively to the deprecating release, either:

* a higher major version number, or
* a higher minor version number, or
* a patchlevel number that is *by at least three* greater.

DNF will log a warning when a deprecated item is used.

This deprecation policy will tighten as the project nears its wide adoption in Fedora.

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

Indices:

* :ref:`genindex`
