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
timer-triggered process are lowered now and shouldn't as noticeably impact the
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

The following bugfixes are included in 0.3.4:

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
fresh librepo. The following issues are now a thing of the past:

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

===================
0.4.8 Release Notes
===================

There are mainly internal changes, new API functions and bugfixes in this release.

Python 3 is fully supported now, the Fedora builds include the Py3 variant. The DNF program still runs under Python 2.7 but the extension authors can now choose what Python they prefer to use.

This is the first version of DNF that deprecates some of its API. Clients using deprecated code will see a message emitted to stderr using the standard `Python warnings module <http://docs.python.org/3.3/library/warnings.html>`_. You can filter out :exc:`dnf.exceptions.DeprecationWarning` to suppress them.

API additions in 0.4.8:

* :attr:`dnf.Base.sack`
* :attr:`dnf.conf.Conf.cachedir`
* :attr:`dnf.conf.Conf.config_file_path`
* :attr:`dnf.conf.Conf.persistdir`
* :meth:`dnf.conf.Conf.read`
* :class:`dnf.package.Package`
* :class:`dnf.query.Query`
* :class:`dnf.subject.Subject`
* :meth:`dnf.repo.Repo.__init__`
* :class:`dnf.sack.Sack`
* :class:`dnf.selector.Selector`
* :class:`dnf.transaction.Transaction`

API deprecations in 0.4.8:

* :mod:`dnf.queries` is deprecated now. If you need to create instances of :class:`.Subject`, import it from :mod:`dnf.subject`. To create :class:`.Query` instances it is recommended to use :meth:`sack.query() <dnf.sack.Sack.query>`.

Bugs fixed in 0.4.8:

* :rhbug:`1014563`
* :rhbug:`1029948`
* :rhbug:`1030998`
* :rhbug:`1030297`
* :rhbug:`1030980`

===================
0.4.9 Release Notes
===================

Several Yum features are revived in this release. ``dnf history rollback`` now works again. The ``history userinstalled`` has been added, it displays a list of ackages that the user manually selected for installation on an installed system and does not include those packages that got installed as dependencies.

We're happy to announce that the API in 0.4.9 has been extended to finally support plugins. There is a limited set of plugin hooks now, we will carefully add new ones in the following releases. New marking operations have ben added to the API and also some configuration options.

An alternative to ``yum shell`` is provided now for its most common use case: :ref:`replacing a non-leaf package with a conflicting package <allowerasing_instead_of_shell>` is achieved by using the ``--allowerasing`` switch now.

API additions in 0.4.9:

* :doc:`api_plugins`
* :ref:`logging_label`
* :meth:`.Base.read_all_repos`
* :meth:`.Base.reset`
* :meth:`.Base.downgrade`
* :meth:`.Base.remove`
* :meth:`.Base.upgrade`
* :meth:`.Base.upgrade_all`
* :attr:`.Conf.pluginpath`
* :attr:`.Conf.reposdir`

API deprecations in 0.4.9:

* :exc:`.PackageNotFoundError` is deprecated for public use. Please catch :exc:`.MarkingError` instead.
* It is deprecated to use :meth:`.Base.install` return value for anything. The method either returns or raises an exception.

Bugs fixed in 0.4.9:

* :rhbug:`884615`
* :rhbug:`963137`
* :rhbug:`991038`
* :rhbug:`1032455`
* :rhbug:`1034607`
* :rhbug:`1036116`

====================
0.4.10 Release Notes
====================

0.4.10 is a bugfix release that also adds some long-requested CLI features and extends the plugin support with two new plugin hooks. An important feature for plugin developers is going to be the possibility to register plugin's own CLI command, available from this version.

``dnf history`` now recognizes ``last`` as a special argument, just like other history commands.

``dnf install`` now accepts group specifications via the ``@`` character.

Support for the ``--setopt`` option has been readded from Yum.

API additions in 0.4.10:

* :doc:`api_cli`
* :attr:`.Plugin.name`
* :meth:`.Plugin.__init__` now specifies the second parameter as an instance of `.cli.Cli`
* :meth:`.Plugin.sack`
* :meth:`.Plugin.transaction`
* :func:`.repo.repo_id_invalid`

API changes in 0.4.10:

* Plugin authors must specify :attr:`.Plugin.name` when authoring a plugin.

Bugs fixed in 0.4.10:

* :rhbug:`967264`
* :rhbug:`1018284`
* :rhbug:`1035164`
* :rhbug:`1036147`
* :rhbug:`1036211`
* :rhbug:`1038403`
* :rhbug:`1038937`
* :rhbug:`1040255`
* :rhbug:`1044502`
* :rhbug:`1044981`
* :rhbug:`1044999`

====================
0.4.11 Release Notes
====================

This is mostly a bugfix release following quickly after 0.4.10, with many updates to documentation.

API additions in 0.4.11:

* :meth:`.Plugin.read_config`
* :class:`.repo.Metadata`
* :attr:`.repo.Repo.metadata`

API changes in 0.4.11:

* :attr:`.Conf.pluginpath` is no longer hard coded but depends on the major Python version.

Bugs fixed in 0.4.11:

* :rhbug:`1048402`
* :rhbug:`1048572`
* :rhbug:`1048716`
* :rhbug:`1048719`
* :rhbug:`1048988`

====================
0.4.12 Release Notes
====================

This release disables fastestmirror by default as we received many complains about it. There are also several bugfixes, most importantly an issue has been fixed that caused packages installed by Anaconda be removed together with a depending package. It is now possible to use ``bandwidth`` and ``throttle`` config values too.

Bugs fixed in 0.4.12:

* :rhbug:`1045737`
* :rhbug:`1048468`
* :rhbug:`1048488`
* :rhbug:`1049025`
* :rhbug:`1051554`

====================
0.4.13 Release Notes
====================

0.4.13 finally ships support for `delta RPMS <https://gitorious.org/deltarpm>`_. Enabling this can save some bandwidth (and use some CPU time) when downloading packages for updates.

Support for bash completion is also included in this version. It is recommended to use the ``generate_completion_cache`` plugin to have the completion work fast. This plugin will be also shipped with ``dnf-plugins-core-0.0.3``.

The :ref:`keepcache <keepcache-label>` config option has been readded.

Bugs fixed in 0.4.13:

* :rhbug:`909468`
* :rhbug:`1030440`
* :rhbug:`1046244`
* :rhbug:`1055051`
* :rhbug:`1056400`

====================
0.4.14 Release Notes
====================

This quickly follows 0.4.13 to address the issue of crashes when DNF output is piped into another program.

API additions in 0.4.14:

* :attr:`.Repo.pkgdir`

Bugs fixed in 0.4.14:

* :rhbug:`1062390`
* :rhbug:`1062847`
* :rhbug:`1063022`
* :rhbug:`1064148`

====================
0.4.15 Release Notes
====================

Massive refactoring of the downloads handling to provide better API for reporting download progress and fixed bugs are the main things brought in 0.4.15.

API additions in 0.4.15:

* :exc:`dnf.exceptions.DownloadError`
* :meth:`dnf.Base.download_packages` now takes the optional `progress` parameter and can raise :exc:`.DownloadError`.
* :class:`dnf.callback.Payload`
* :class:`dnf.callback.DownloadProgress`
* :meth:`dnf.query.Query.filter` now also recognizes ``provides`` as a filter name.

Bugs fixed in 0.4.15:

* :rhbug:`1048788`
* :rhbug:`1065728`
* :rhbug:`1065879`
* :rhbug:`1065959`
* :rhbug:`1066743`

====================
0.4.16 Release Notes
====================

The refactorings from 0.4.15 are introducing breakage causing the background ``dnf makecache`` runs traceback. This release fixes that.

Bugs fixed in 0.4.16:

* :rhbug:`1069996`

====================
0.4.17 Release Notes
====================

This release fixes many bugs in the downloads/DRPM CLI area. A bug got fixed preventing a regular user from running read-only operations using ``--cacheonly``. Another fix ensures that ``metadata_expire=never`` setting is respected. Lastly, the release provides three requested API calls in the repo management area.

API additions in 0.4.17:

* :meth:`dnf.repodict.RepoDict.all`
* :meth:`dnf.repodict.RepoDict.get_matching`
* :meth:`dnf.repo.Repo.set_progress_bar`

Bugs fixed in 0.4.17:

* :rhbug:`1059704`
* :rhbug:`1058224`
* :rhbug:`1069538`
* :rhbug:`1070598`
* :rhbug:`1070710`
* :rhbug:`1071323`
* :rhbug:`1071455`
* :rhbug:`1071501`
* :rhbug:`1071518`
* :rhbug:`1071677`

====================
0.4.18 Release Notes
====================

Support for ``dnf distro-sync <spec>`` finally arrives in this version.

DNF has moved to handling groups as objects,  tagged installed/uninstalled independently from the actual installed packages. This has been in Yum as the ``group_command=objects`` setting and the default in recent Fedora releases. There are API extensions related to this change as well as two new CLI commands: ``group mark install`` and ``group mark remove``.

API items deprecated in 0.4.8 and 0.4.9 have been dropped in 0.4.18, in accordance with our :ref:`deprecating-label`.

API changes in 0.4.18:

* :mod:`dnf.queries` has been dropped as announced in `0.4.8 Release Notes`_
* :exc:`dnf.exceptions.PackageNotFoundError` has been dropped from API as announced in `0.4.9 Release Notes`_
* :meth:`dnf.Base.install` no longer has to return the number of marked packages as announced in `0.4.9 Release Notes`_

API deprecations in 0.4.18:

* :meth:`dnf.Base.select_group` is deprecated now. Please use :meth:`~.Base.group_install` instead.

API additions in 0.4.18:

* :meth:`dnf.Base.group_install`
* :meth:`dnf.Base.group_remove`

Bugs fixed in 0.4.18:

* :rhbug:`963710`
* :rhbug:`1067136`
* :rhbug:`1071212`
* :rhbug:`1071501`

====================
0.4.19 Release Notes
====================

Arriving one week after 0.4.18, the 0.4.19 mainly provides a fix to a traceback in group operations under non-root users.

DNF starts to ship separate translation files (.mo) starting with this release.

Bugs fixed in 0.4.19:

* :rhbug:`1077173`
* :rhbug:`1078832`
* :rhbug:`1079621`

===================
0.5.0 Release Notes
===================

The biggest improvement in 0.5.0 is complete support for groups `and environments <https://bugzilla.redhat.com/show_bug.cgi?id=1063666>`_, including internal database of installed groups independent of the actual packages (concept known as groups-as-objects from Yum). Upgrading groups is supported now with ``group upgrade`` too.

To force refreshing of metadata before an operation (even if the data is not expired yet), `the refresh option has been added <https://bugzilla.redhat.com/show_bug.cgi?id=1064226>`_.

Internally, the CLI went through several changes to allow for better API accessibility like `granular requesting of root permissions <https://bugzilla.redhat.com/show_bug.cgi?id=1062889>`_.

API has got many more extensions, focusing on better manipulation with comps and packages. There are new entries in :doc:`cli_vs_yum` and :doc:`user_faq` too.

Several resource leaks (file descriptors, noncollectable Python objects) were found and fixed.

API changes in 0.5.0:

* it is now recommended that either :meth:`dnf.Base.close` is used, or that :class:`dnf.Base` instances are treated as a context manager.

API extensions in 0.5.0:

* :meth:`dnf.Base.add_remote_rpm`
* :meth:`dnf.Base.close`
* :meth:`dnf.Base.group_upgrade`
* :meth:`dnf.Base.resolve` optionally accepts `allow_erasing` arguments now.
* :meth:`dnf.Base.package_downgrade`
* :meth:`dnf.Base.package_install`
* :meth:`dnf.Base.package_upgrade`
* :class:`dnf.cli.demand.DemandSheet`
* :attr:`dnf.cli.Command.base`
* :attr:`dnf.cli.Command.cli`
* :attr:`dnf.cli.Command.summary`
* :attr:`dnf.cli.Command.usage`
* :meth:`dnf.cli.Command.configure`
* :attr:`dnf.cli.Cli.demands`
* :class:`dnf.comps.Package`
* :meth:`dnf.comps.Group.packages_iter`
* :data:`dnf.comps.MANDATORY` etc.

Bugs fixed in 0.5.0:

* :rhbug:`1029022`
* :rhbug:`1051869`
* :rhbug:`1061780`
* :rhbug:`1062884`
* :rhbug:`1062889`
* :rhbug:`1063666`
* :rhbug:`1064211`
* :rhbug:`1064226`
* :rhbug:`1073859`
* :rhbug:`1076884`
* :rhbug:`1079519`
* :rhbug:`1079932`
* :rhbug:`1080331`
* :rhbug:`1080489`
* :rhbug:`1082230`
* :rhbug:`1083432`
* :rhbug:`1083767`
* :rhbug:`1084139`
* :rhbug:`1084553`
* :rhbug:`1088166`

===================
0.5.1 Release Notes
===================

Bugfix release with several internal cleanups. One outstanding change for CLI users is that DNF is a lot less verbose now during the dependency resolving phase.

Bugs fixed in 0.5.1:

* :rhbug:`1065882`
* :rhbug:`1081753`
* :rhbug:`1089864`

===================
0.5.2 Release Notes
===================

This release brings `autoremove command <https://bugzilla.redhat.com/show_bug.cgi?id=963345>`_ that removes any package that was originally installed as a dependency (e.g. had not been specified as an explicit argument to the install command) and is no longer needed.

Enforced verification of SSL connections can now be disabled with the :ref:`sslverify setting <sslverify-label>`.

We have been plagued with many crashes related to Unicode and encodings since the 0.5.0 release. These have been cleared out now.

There's more: improvement in startup time, `extended globbing semantics for input arguments <https://bugzilla.redhat.com/show_bug.cgi?id=1083679>`_ and `better search relevance sorting <https://bugzilla.redhat.com/show_bug.cgi?id=1093888>`_.

Bugs fixed in 0.5.2

* :rhbug:`963345`
* :rhbug:`1073457`
* :rhbug:`1076045`
* :rhbug:`1083679`
* :rhbug:`1092006`
* :rhbug:`1092777`
* :rhbug:`1093888`
* :rhbug:`1094594`
* :rhbug:`1095580`
* :rhbug:`1095861`
* :rhbug:`1096506`
