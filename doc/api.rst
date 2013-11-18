###################
 DNF API Reference
###################

.. contents::

==============
 Introduction
==============

The provided Python API to DNF is supposed to mainly allow writing the following two categories of programs:

1. plugins to DNF which extend functionality of the system's DNF installation.
2. extension applications that embed DNF to perform specific package management tasks.

.. NOTE::

  The API consists of exactly those elements described in this document, items not documented here can change release to release. Opening a `bugzilla`_ if certain needed functionality is not exposed is the right thing to do.

.. _deprecating-label:

====================
 Deprecation Policy
====================

.. WARNING::

  The DNF project has not fully stabilized yet and it is possible parts the API described in this document can change. All such changes are documented per-version in the release notes and are subject to our deprecation policy. We do our best to reduce their number to a necessary minimum.

Depracated API items (classes, methods, etc.) are designated as such in the relese notes. The first release where support for such items can be dropped entirely must be issued at least three months after the issue of the release that announced the deprecation and at the same time have, relatively to the deprecating release, either:

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

Indices:

* :ref:`genindex`
