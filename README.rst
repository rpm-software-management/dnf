#####
 DNF
#####

This is a preview of the next major version of `Yum
<http://yum.baseurl.org/>`_. It does package management using `RPM
<http://rpm.org/>`_, `libsolv <https://github.com/openSUSE/libsolv>`_ and
`hawkey <https://github.com/akozumpl/hawkey>`_ libraries. For metadata handling
and package downloads it utilizes `librepo
<https://github.com/tojaj/librepo>`_. To process and effectively handle the
comps data we have `libcomps <https://github.com/midnightercz/libcomps>`_.

============
 Installing
============

DNF and all its dependencies are available in Fedora 18 and later, including the
rawhide Fedora. You can install DNF from the distribution repositories there::

    sudo yum install dnf

In other RPM-based distributions you need to build all the components from their
sources.

===============
 Documentation
===============

The DNF package contains man pages, dnf(8) and dnf.conf(8). It is also possible
to `read the DNF documentation <http://akozumpl.github.io/dnf/>`_ from your
browser. There's also a `wiki <https://github.com/akozumpl/dnf/wiki>`_ meant for
contributors to DNF and related projects.

====================
 Bug reporting etc.
====================

Please report any bugs to the `Red Hat bugzilla <https://bugzilla.redhat.com/>`_,
make sure to check the issue has not been fixed in a later version. Freenode's
irc channel ``#yum`` is meant for discussions related to both Yum and DNF.
