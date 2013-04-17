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
