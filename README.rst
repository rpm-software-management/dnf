###############
 Dandified YUM
###############

.. image:: https://raw.githubusercontent.com/rpm-software-management/dnf/gh-pages/logos/DNF_logo.png
 
Dandified YUM (DNF) is the next upcoming major version of `YUM <http://yum.baseurl.org/>`_. It does package management using `RPM <http://rpm.org/>`_, `libsolv <https://github.com/openSUSE/libsolv>`_ and `hawkey <https://github.com/rpm-software-management/hawkey>`_ libraries. For metadata handling and package downloads it utilizes `librepo <https://github.com/tojaj/librepo>`_. To process and effectively handle the comps data it uses `libcomps <https://github.com/midnightercz/libcomps>`_.

============
 Installing
============

DNF and all its dependencies are available in Fedora 18 and later, including the
rawhide Fedora.

Optionally you can use repositories with DNF nightly builds for last 2 stable Fedora versions available at copr://rpmsoftwaremanagement/dnf-nightly. You can enable the repository e.g. using:: 

    dnf copr enable rpmsoftwaremanagement/dnf-nightly

Then install DNF typing::

    sudo yum install dnf

In other RPM-based distributions you need to build all the components from their
sources.

======================
 Building from source
======================

All commands should be run from the DNF git checkout directory.

To install the build dependencies::

    sudo dnf builddep dnf.spec

To build DNF::

    mkdir build;
    pushd build;
    cmake ..; # add '-DPYTHON_DESIRED="3"' option for Python 3 build
    make;
    popd;

To run DNF when compiled for Python2::

    PYTHONPATH=`readlink -f .` bin/dnf-2 <arguments>

To run DNF when compiled for Python3::

    PYTHONPATH=`readlink -f .` bin/dnf-3 <arguments>

If you want to build the manpages, use the option ``-DWITH_MAN=0`` with cmake.

Man pages will be located in ``build/doc`` and can be read with ``man -l``, e.g::

    man -l build/doc/dnf.8

=============================
 Building and installing rpm
=============================

From the DNF git checkout directory::
    
    cmake .
    ./package/build-test-rpm
    sudo rpm -i ~/rpmbuild/RPMS/noarch/dnf-<version>-<release>.noarch.rpm

===============
 Running tests
===============

From the DNF git checkout directory::

    mkdir build;
    pushd build;
    cmake .. && make ARGS="-V" test;
    popd;

==============
 Contribution
==============

Here's the most direct way to get your work merged into the project.

1. Fork the project
#. Clone down your fork
#. Implement your feature or bug fix and commit changes
#. If you reported a bug or you know it fixes existing bug at `Red Hat bugzilla <https://bugzilla.redhat.com/>`_, append ``(RhBug:<bug_id>)`` to your commit message
#. In special commit add your name and email under ``DNF CONTRIBUTORS`` section in `authors file <https://github.com/rpm-software-management/dnf/blob/master/AUTHORS>`_ as a reward for your generosity
#. Push the branch up to your fork
#. Send a pull request for your branch

Please, do not create the pull requests with translation (.po) files improvements. Fix the translation on `Zanata <https://fedora.zanata.org/iteration/view/dnf/master>`_ instead.

===============
 Documentation
===============

The DNF package distribution contains man pages, dnf(8) and dnf.conf(8). It is also possible to `read the DNF documentation <http://dnf.readthedocs.org>`_ online, the page includes API documentation. There's also a `wiki <https://github.com/rpm-software-management/dnf/wiki>`_ meant for contributors to DNF and related projects.

====================
 Bug reporting etc.
====================

Please report discovered bugs to the `Red Hat bugzilla <https://bugzilla.redhat.com/>`_ following this `guide <https://github.com/rpm-software-management/dnf/wiki/Bug-Reporting>`_. If you planned to propose the patch in the report, consider `Contribution`_ instead.

Freenode's irc channel ``#yum`` is meant for discussions related to both YUM and DNF. Questions should be asked there, issues discussed. Remember: ``#yum`` is not a support channel and prior research is expected from the questioner.
