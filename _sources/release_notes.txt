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
