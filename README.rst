###############
 Dandified Yum
###############

Dandified Yum (DNF) is the next upcoming major version of `Yum <http://yum.baseurl.org/>`_. It does package management using `RPM <http://rpm.org/>`_, `libsolv <https://github.com/openSUSE/libsolv>`_ and `hawkey <https://github.com/rpm-software-management/hawkey>`_ libraries. For metadata handling and package downloads it utilizes `librepo <https://github.com/tojaj/librepo>`_. To process and effectively handle the comps data it uses `libcomps <https://github.com/midnightercz/libcomps>`_.

============
 Installing
============

DNF and all its dependencies are available in Fedora 18 and later, including the
rawhide Fedora. You can install DNF from the distribution repositories there::

    sudo yum install dnf

In other RPM-based distributions you need to build all the components from their
sources.

======================
 Building from source
======================

From the DNF git checkout directory::

    mkdir build;
    pushd build;
    cmake .. && make;
    popd;

Then to run DNF::

    PYTHONPATH=`readlink -f .` bin/dnf <arguments>

===============
 Running tests
===============

From the DNF git checkout directory::

    mkdir build;
    pushd build;
    cmake .. && make ARGS="-V" test;
    popd;

===============
 Documentation
===============

The DNF package distribution contains man pages, dnf(8) and dnf.conf(8). It is also possible to `read the DNF documentation <http://dnf.readthedocs.org>`_ online, the page includes API documentation. There's also a `wiki <https://github.com/rpm-software-management/dnf/wiki>`_ meant for contributors to DNF and related projects.

====================
 Bug reporting etc.
====================

Please report discovered bugs to the `Red Hat bugzilla <https://bugzilla.redhat.com/>`_.

Freenode's irc channel ``#yum`` is meant for discussions related to both Yum and DNF. Questions should be asked there, issues discussed. Remember: ``#yum`` is not a support channel and prior research is expected from the questioner.
