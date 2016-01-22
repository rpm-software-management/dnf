###############
 Dandified Yum
###############

Dandified Yum (DNF) is the next upcoming major version of `Yum <http://yum.baseurl.org/>`_. It does package management using `RPM <http://rpm.org/>`_, `libsolv <https://github.com/openSUSE/libsolv>`_ and `hawkey <https://github.com/rpm-software-management/hawkey>`_ libraries. For metadata handling and package downloads it utilizes `librepo <https://github.com/tojaj/librepo>`_. To process and effectively handle the comps data it uses `libcomps <https://github.com/midnightercz/libcomps>`_.

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

From the DNF git checkout directory::

    mkdir build;
    pushd build;
    cmake -DUSE_CHECKOUT=ON .. && make;
    popd;

Then to run DNF::

    build/bin/dnf <arguments>

To build DNF for Python 3, use the option ``-DPYTHON_DESIRED:str=3`` with
cmake.

If you're also developing some plugins, you can make your DNF build aware of
them by using the following option when building::

    -DPLUGINPATH="/path/to/plugins:/another/one"

You can also specify ``PYTHONPATH`` that your DNF build will use.  This is
useful if you want to use your checkout of a dependency like libcomps::

    -DPYTHONPATH="/path/to/libcomps/build:/something/else"

To use the shipped bash completion::

    source etc/bash_completion.d/dnf

Note that the completion will only work from within the build directory.  To
make it work globally, add the build directory to your ``PYTHONPATH``.

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

From the build directory::

    make ARGS="-V" test

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

===============
 Documentation
===============

The DNF package distribution contains man pages, dnf(8) and dnf.conf(8). It is also possible to `read the DNF documentation <http://dnf.readthedocs.org>`_ online, the page includes API documentation. There's also a `wiki <https://github.com/rpm-software-management/dnf/wiki>`_ meant for contributors to DNF and related projects.

====================
 Bug reporting etc.
====================

Please report discovered bugs to the `Red Hat bugzilla <https://bugzilla.redhat.com/>`_ following this `guide <https://github.com/rpm-software-management/dnf/wiki/Bug-Reporting>`_. If you planned to propose the patch in the report, consider `Contribution`_ instead.

Freenode's irc channel ``#yum`` is meant for discussions related to both Yum and DNF. Questions should be asked there, issues discussed. Remember: ``#yum`` is not a support channel and prior research is expected from the questioner.
