###################
 DNF Release Notes
###################

.. contents::

===================
0.3.1 Release Notes
===================

0.3.1 brings mainly changes to the automatic metadata synchronization. In
Fedora, ``dnf makecache`` is triggered via SystemD timers now and takes an
optional ``background`` extra-argument to run in resource-considerate mode (no
syncing when running on laptop battery, only actually performing the check at
most once every three hours). Also, the IO and CPU priorities of the
timer-triggered process are lowered now and shouldn't as noticably impact the
system's performance.

The administrator can also easily disable the automatic metadata updates by
setting :ref:`metadata_timer_sync <metadata_timer_sync-label>` to 0.

The default value of :ref:`metadata_expire <metadata_expire-label>` was
increased from 6 hours to 48 hours. In Fedora, the repos usually set this
explicitly so this change is not going to cause much impact.

The following reported issues are fixed in this release:

* :rhbug:`916657`
* :rhbug:`921294`
* :rhbug:`922521`
* :rhbug:`926871`
* :rhbug:`878826`
* :rhbug:`922664`
* :rhbug:`892064`
* :rhbug:`919769`

===================
0.3.2 Release Notes
===================

The major improvement in this version is in speeding up syncing of repositories
using metalink by looking at the repomd.xml checksums. This effectively lets DNF
cheaply refresh expired repositories in cases where the original has not
changed\: for instance the main Fedora repository is refreshed with one 30 kB
HTTP download. This functionality is present in the current Yum but hasn't
worked in DNF since 3.0.0.

Otherwise this is mainly a release fixing bugs and tracebacks. The following
reported bugs are fixed:

* :rhbug:`947258`
* :rhbug:`889202`
* :rhbug:`923384`

===================
0.3.3 Release Notes
===================

The improvements in 0.3.3 are only API changes to the logging. There is a new
module ``dnf.logging`` that defines simplified logging structure compared to
Yum, with fewer logging levels and `simpler usage for the developers
<https://github.com/akozumpl/dnf/wiki/Hacking#logging>`_. The RPM transaction logs are
no longer in ``/var/log/dnf.transaction.log`` but in ``/var/log/dnf.rpm.log`` by
default.

The exception classes were simplified and moved to ``dnf.exceptions``.

The following bugs are fixed in 0.3.3:

* :rhbug:`950722`
* :rhbug:`903775`

===================
0.3.4 Release Notes
===================

0.3.4 is the first DNF version since the fork from Yum that is able to
manipulate the comps data. In practice, ``dnf group install <group name>`` works
again. No other group commands are supported yet.

Support for ``librepo-0.0.4`` and related cleanups and extensions this new
version allows are included (see the buglist below)

This version has also improved reporting of obsoleted packages in the CLI (the
Yum-style "replacing <package-nevra>" appears in the textual transaction
overview).

The follwoing bugfixes are included in 0.3.4:

* :rhbug:`887317`
* :rhbug:`914919`
* :rhbug:`922667`

===================
0.3.5 Release Notes
===================

Besides few fixed bugs this version should not present any differences for the
user. On the inside, the transaction managing mechanisms have changed
drastically, bringing code simplification, better maintainability and better
testability.

In Fedora, there is a change in the spec file effectively preventing the
makecache timer from running *immediatelly after installation*. The timer
service is still enabled by default, but unless the user starts it manually with
``systemctl start dnf-makecache.timer`` it will not run until after the first
reboot. This is in alignment with Fedora packaging best practices.

The following bugfixes are included in 0.3.5:

* :rhbug:`958452`
* :rhbug:`959990`
* :rhbug:`961549`
* :rhbug:`962188`

===================
0.3.6 Release Notes
===================

This is a bugfix release, including the following fixes:

* :rhbug:`966372`
* :rhbug:`965410`
* :rhbug:`963627`
* :rhbug:`965114`
* :rhbug:`964467`
* :rhbug:`963680`
* :rhbug:`963133`

===================
0.3.7 Release Notes
===================

This is a bugfix release:

* :rhbug:`916662`
* :rhbug:`967732`

===================
0.3.8 Release Notes
===================

A new locking module has been integrated in this version, clients should see the
message about DNF lock being taken less often.

Panu Matilainen has submitted many patches to this release to cleanup the RPM
interfacing modules.

The following bugs are fixed in this release:

* :rhbug:`908491`
* :rhbug:`968159`
* :rhbug:`974427`
* :rhbug:`974866`
* :rhbug:`976652`
* :rhbug:`975858`

===================
0.3.9 Release Notes
===================

This is a quick bugfix release dealing with reported bugs and tracebacks:

* :rhbug:`964584`
* :rhbug:`979942`
* :rhbug:`980227`
* :rhbug:`981310`

====================
0.3.10 Release Notes
====================

The only major change is that ``skip_if_unavailable`` is :ref:`enabled by
default now <skip_if_unavailable_default>`.

A minor release otherwise, mainly to get a new version of DNF out that uses a
fresh librepo. The follwoing issues are now a thing of the past:

* :rhbug:`977661`
* :rhbug:`984483`
* :rhbug:`986545`

====================
0.3.11 Release Notes
====================

The default multilib policy configuration value is ``best`` now. This does not
pose any change for the Fedora users because exactly the same default had been
previously achieved by a setting in ``/etc/dnf/dnf.conf`` shipped with the
Fedora package.

An important fix to the repo module speeds up package downloads again is present
in this release. The full list of fixes is:

* :rhbug:`979042`
* :rhbug:`977753`
* :rhbug:`996138`
* :rhbug:`993916`

===================
0.4.0 Release Notes
===================

The new minor version brings many internal changes to the comps code, most comps
parsing and processing is now delegated to `libcomps
<https://github.com/midnightercz/libcomps>`_ by Jindřich Luža.

The ``overwrite_groups`` config option has been dropped in this version and DNF
acts if it was 0, that is groups with the same name are merged together.

The currently supported groups commands (``group list`` and ``group install``)
are documented on the manpage now.

The 0.4.0 version is the first one supported by the DNF Payload for Anaconda and
many changes since 0.3.11 make that possible by cleaning up the API and making
it more sane (cleanup of ``yumvars`` initialization API, unifying the RPM
transaction callback objects hierarchy, slimming down ``dnf.rpmUtils.arch``,
improved logging).

Fixes for the following are contained in this version:

* :rhbug:`997403`
* :rhbug:`1002508`
* :rhbug:`1002798`

===================
0.4.1 Release Notes
===================

The focus of this release was to support our efforts in implementing the DNF
Payload for Anaconda, with changes on the API side of things (better logging,
new ``Base.reset()`` method).

Support for some irrelevant config options has been dropped (``kernelpkgnames``,
``exactarch``, ``rpm_check_debug``). We also no longer detect metalinks in the
``mirrorlist`` option (see `Fedora bug 948788
<https://bugzilla.redhat.com/show_bug.cgi?id=948788>`_).

DNF is on its way to drop the urlgrabber dependency and the first set of patches
towards this goal is already in.

Expect the following bugs to go away with upgrade to 0.4.1:

* :rhbug:`998859`
* :rhbug:`1006366`
* :rhbug:`1008444`
* :rhbug:`1003220`

===================
0.4.2 Release Notes
===================

DNF now downloads packages for the transaction in parallel with progress bars
updated to effectively represent this. Since so many things in the downloading
code were changing, we figured it was a good idea to finally drop urlgrabber
dependency at the same time. Indeed, this is the first version that doesn't
require urlgrabber for neither build nor run.

Similarly, since `librepo started to support this
<https://github.com/Tojaj/librepo/commit/acf458f29f7234d2d8d93a68391334343beae4b9>`_,
downloads in DNF now use the fastests mirrors available by default.

The option to :ref:`specify repositories' costs <repo_cost-label>` has been
readded.

Internally, DNF has seen first part of ongoing refactorings of the basic
operations (install, update) as well as a couple of new API methods supporting
development of extensions.

These bugzillas are fixed in 0.4.2:

* :rhbug:`909744`
* :rhbug:`984529`
* :rhbug:`967798`
* :rhbug:`995459`

===================
0.4.3 Release Notes
===================

This is an early release to get the latest DNF out with the latest librepo
fixing the `Too many open files
<https://bugzilla.redhat.com/show_bug.cgi?id=1015957>`_ bug.

In Fedora, the spec file has been updated to no longer depend on precise
versions of the libraries so in the future they can be released
independently.

This release sees the finished refactoring in error handling during basic
operations and adds support for ``group remove`` and ``group info`` commands,
i.e. the following two bugs:

* :rhbug:`1013764`
* :rhbug:`1013773`

===================
0.4.4 Release Notes
===================

The initial support for Python 3 in DNF has been merged in this version. In
practice one can not yet run the ``dnf`` command in Py3 but the unit tests
already pass there. We expect to give Py3 and DNF heavy testing during the
Fedora 21 development cycle and eventually switch to it as the default. The plan
is to drop Python 2 support as soon as Anaconda is running in Python 3.

Minor adjustments to allow Anaconda support also happened during the last week,
as well as a fix to a possibly severe bug that one is however not really likely
to see with non-devel Fedora repos:

* :rhbug:`1017278`

===================
0.4.5 Release Notes
===================

A serious bug causing `tracebacks during package downloads
<https://bugzilla.redhat.com/show_bug.cgi?id=1021087>`_ made it into 0.4.4 and
this release contains a fix for that. Also, a basic proxy support has been
readded now.

Bugs fixed in 0.4.5:

* :rhbug:`1021087`

===================
0.4.6 Release Notes
===================

0.4.6 brings two new major features. Firstly, it is the revival of ``history
undo``, so transactions can be reverted now.  Secondly, DNF will now limit the
number of installed kernels and *installonly* packages in general to the number
specified by :ref:`installonly_limit <installonly-limit-label>` configuration
option.

DNF now supports the ``group summary`` command and one-word group commands no
longer cause tracebacks, e.g. ``dnf grouplist``.

There are vast internal changes to ``dnf.cli``, the subpackge that provides CLI
to DNF. In particular, it is now better separated from the core.

The hawkey library used against DNF from with this versions uses a `recent RPMDB
loading optimization in libsolv
<https://github.com/openSUSE/libsolv/commit/843dc7e1>`_ that shortens DNF
startup by seconds when the cached RPMDB is invalid.

We have also added further fixes to support Python 3 and enabled `librepo's
fastestmirror caching optimization
<https://github.com/Tojaj/librepo/commit/b8a063763ccd8a84b8ec21a643461eaace9b9c08>`_
to tighten the download times even more.

Bugs fixed in 0.4.6:

* :rhbug:`878348`
* :rhbug:`880524`
* :rhbug:`1019957`
* :rhbug:`1020101`
* :rhbug:`1020934`
* :rhbug:`1023486`

===================
0.4.7 Release Notes
===================

We start to publish the :doc:`api` with this release. It is largely
incomprehensive at the moment, yet outlines the shape of the documentation and
the process the project is going to use to maintain it.

There are two Yum configuration options that were dropped: :ref:`group_package_types <group_package_types_dropped>` and :ref:`upgrade_requirements_on_install <upgrade_requirements_on_install_dropped>`.

Bugs fixed in 0.4.7:

* :rhbug:`1019170`
* :rhbug:`1024776`
* :rhbug:`1025650`
