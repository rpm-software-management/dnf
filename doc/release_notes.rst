..
  Copyright (C) 2014-2016 Red Hat, Inc.

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
2.0.0 Release Notes
===================

List of all incompatible changes can be found at: :doc:`dnf-1 vs dnf-2 <dnf-1_vs_dnf-2>`

API changes in 2.0.0:

* :meth:`dnf.Base.add_remote_rpms` now suppresses any error if :attr:`strict` equals to ``False``.
* :meth:`dnf.Base.read_comps` now limits results to system basearch if :attr:`arch_filter` equals to ``True``.
* :meth:`dnf.cli.Cli.configure` now doesn't take any additional arguments.
* :meth:`dnf.cli.Cli.run` now doesn't take any additional arguments.
* :meth:`dnf.Plugin.read_config` now doesn't take any name of config file.
* :meth:`dnf.Repo.__init__` now takes `parent_conf` argument which is an instance of :class:`dnf.conf.Conf` holding main dnf configuration instead of `cachedir` path.
* ``exclude`` and ``include`` configuration options change to ``excludepkgs`` and ``includepkgs``.

API additions in 2.0.0:

* :meth:`dnf.Base.init_plugins` initializes plugins. It is possible to disable some plugins by passing the list of their name patterns to :attr:`disabled_glob`.
* :meth:`dnf.Base.configure_plugins` configures plugins by running their :meth:`configure` method.
* :meth:`dnf.Base.urlopen` opens the specified absolute ``url`` and returns a file object which respects proxy setting even for non-repo downloads
* Introduced new configuration options: ``clean_requirements_on_remove``, ``deltarpm_percentage``, ``exit_on_lock``, ``get_reposdir``, ``group_package_types``, ``installonlypkgs``, ``keepcache``, ``protected_packages``, ``retries`` and ``upgrade_group_objects_upgrade``. For detailed description see: :doc:`DNF API <api_conf>`.
* Introduced new configuration methods: :meth:`dump` and :meth:`write_raw_configfile`. For detailed description see: :doc:`DNF API <api_conf>`.
* Introduced :class:`dnf.package.Package` attributes :attr:`debug_name`, :attr:`downloadsize`, :attr:`source_debug_name` and :attr:`source_name`. For detailed description see: :doc:`DNF Package API <api_package>`.
* :meth:`dnf.Query.extras` returns a new query that limits the result to installed packages that are not present in any repo.
* :meth:`dnf.Repo.enable_debug_repos` enables debug repos corresponding to already enabled binary repos.
* :meth:`dnf.Repo.enable_source_repos` enables source repos corresponding to already enabled binary repos.
* :meth:`dnf.Repo.dump` prints repository configuration, including inherited values.

DNF command changes in 2.0.0:

* ``dnf [options] group install [with-optional] <group-spec>...`` changes to ``dnf [options] group install [--with-optional] <group-spec>...``.
* ``dnf [options] list command [<package-name-specs>...]`` changes to `dnf [options] list --command [<package-name-specs>...]``.
* ``dnf [options] makecache timer`` changes to ``dnf [options] makecache --timer``.
* ``dnf [options] repolist [enabled|disabled|all]`` changes to ``dnf [options] repolist [--enabled|--disabled|--all]``.
* ``dnf [options] repository-packages <repoid> info command [<package-name-spec>...]`` changes to ``dnf [options] repository-packages <repoid> info --command [<package-name-spec>...]``.
* ``dnf [options] search [all] <keywords>...`` changes to ``dnf [options] search [--all] <keywords>...``.
* ``dnf [options] updateinfo [<availability>] [<spec>...]`` changes to ``dnf [options] updateinfo [--summary|--list|--info] [<availability>] [<spec>...]``.
* ``--disablerepo`` :doc:`command line argument <command_ref>` is mutually exclusive with ``--repo``.
* ``--enablerepo`` :doc:`command line argument <command_ref>` now appends repositories.
* ``--installroot`` :doc:`command line argument <command_ref>`. For detailed description see: :doc:`DNF command API <command_ref>`.
* ``--releasever`` :doc:`command line argument <command_ref>` now doesn't detect release number from running system.
* ``--repofrompath`` :doc:`command line argument <command_ref>` can now be combined with ``--repo`` instead of ``--enablerepo``.

DNF command additions in 2.0.0:

* ``dnf [options] remove --duplicates`` removes older version of duplicated packages.
* ``dnf [options] remove --oldinstallonly``removes old installonly packages keeping only ``installonly_limit`` latest versions.
* ``dnf [options] repoquery [<select-options>] [<query-options>] [<pkg-spec>]`` searches the available DNF repositories for selected packages and displays the requested information about them. It is an equivalent of ``rpm -q`` for remote repositories.
* ``dnf [options] repoquery --querytags`` provides list of recognized tags by repoquery option \-\ :ref:`-queryformat <queryformat_repoquery-label>`.
* ``--repo`` :doc:`command line argument <command_ref>` enables just specific repositories by an id or a glob. Can be used multiple times with accumulative effect. It is basically shortcut for ``--disablerepo="*" --enablerepo=<repoid>`` and is mutually exclusive with ``--disablerepo`` option.

Bugs fixed in 2.0.0:

* :rhbug:`1348766`
* :rhbug:`1337731`
* :rhbug:`1333591`
* :rhbug:`1314961`
* :rhbug:`1372307`
* :rhbug:`1373108`
* :rhbug:`1148627`
* :rhbug:`1267298`
* :rhbug:`1373591`
* :rhbug:`1230355`
* :rhbug:`1366793`
* :rhbug:`1369411`
* :rhbug:`1366793`
* :rhbug:`1369459`
* :rhbug:`1306096`
* :rhbug:`1368832`
* :rhbug:`1366793`
* :rhbug:`1359016`
* :rhbug:`1365593`
* :rhbug:`1297087`
* :rhbug:`1227053`
* :rhbug:`1356926`
* :rhbug:`1055910`
* :rhbug:`1219867`
* :rhbug:`1226677`
* :rhbug:`1350604`
* :rhbug:`1253120`
* :rhbug:`1158548`
* :rhbug:`1262878`
* :rhbug:`1318852`
* :rhbug:`1327438`
* :rhbug:`1343880`
* :rhbug:`1338921`
* :rhbug:`1284349`
* :rhbug:`1338921`
* :rhbug:`1284349`
* :rhbug:`1306096`
* :rhbug:`1218071`
* :rhbug:`1193823`
* :rhbug:`1246211`
* :rhbug:`1193851`
* :rhbug:`1158548`
* :rhbug:`1215208`
* :rhbug:`1212693`
* :rhbug:`1212341`
* :rhbug:`1306591`
* :rhbug:`1227001`
* :rhbug:`1163028`
* :rhbug:`1279185`
* :rhbug:`1289067`
* :rhbug:`1328674`
* :rhbug:`1380580`

====================
1.1.10 Release Notes
====================

Fixed unicode handling and fixing other bugs.

Bugs fixed in 1.1.10:

* :rhbug:`1257965`
* :rhbug:`1352130`
* :rhbug:`1343764`
* :rhbug:`1308994`
* :rhbug:`1230183`
* :rhbug:`1295090`
* :rhbug:`1325869`
* :rhbug:`1338046`
* :rhbug:`1214768`
* :rhbug:`1338504`
* :rhbug:`1338564`

===================
1.1.9 Release Notes
===================

From this release if you use any non-API methods warning will be printed and
bugfixes.

Bugs fixed in 1.1.9:

* :rhbug:`1324086`
* :rhbug:`1332012`
* :rhbug:`1292892`
* :rhbug:`1328674`
* :rhbug:`1286556`
* :rhbug:`1245121`

===================
1.1.8 Release Notes
===================

Improvements in documentation, bugfixes, translation updates.

Bugs fixed in 1.1.8:

* :rhbug:`1309408`
* :rhbug:`1209649`
* :rhbug:`1272977`
* :rhbug:`1322226`
* :rhbug:`1315349`
* :rhbug:`1214562`
* :rhbug:`1313215`
* :rhbug:`1306057`
* :rhbug:`1289164`

===================
1.1.7 Release Notes
===================

Added :meth:`dnf.rpm.basearch` method, intended for the detection of CPU base architecture.

The :ref:`group list <grouplist_command-label>` command was enriched with ``installed`` and ``available`` switches.

Documented a standard way of overriding autodetected arhitectures in :doc:`DNF API <api_conf>`.

Bugs fixed in 1.1.7:

* :rhbug:`1286477`
* :rhbug:`1305356`
* :rhbug:`1258503`
* :rhbug:`1283432`
* :rhbug:`1268818`
* :rhbug:`1306304`
* :rhbug:`1302934`
* :rhbug:`1303149`
* :rhbug:`1302217`

===================
1.1.6 Release Notes
===================

Added support of socks5 proxy.

Bugs fixed in 1.1.6:

* :rhbug:`1291895`
* :rhbug:`1256587`
* :rhbug:`1287221`
* :rhbug:`1277360`
* :rhbug:`1294241`
* :rhbug:`1289166`
* :rhbug:`1294355`
* :rhbug:`1226322`
* :rhbug:`1275878`
* :rhbug:`1239274`

===================
1.1.5 Release Notes
===================

Improved the start-up time of bash completion.

Reviewed documentation.

Bugs fixed in 1.1.5:

* :rhbug:`1286619`
* :rhbug:`1229046`
* :rhbug:`1282250`
* :rhbug:`1265391`
* :rhbug:`1283017`
* :rhbug:`1278592`
* :rhbug:`1260421`
* :rhbug:`1278382`
* :rhbug:`1230820`
* :rhbug:`1280240`

===================
1.1.4 Release Notes
===================

API additions in 1.1.4:

* newly added :meth:`dnf.Query.duplicated`
* extended :meth:`dnf.Query.latest`

Bugs fixed in 1.1.4:

* :rhbug:`1278031`
* :rhbug:`1264032`
* :rhbug:`1209056`
* :rhbug:`1274946`

===================
1.1.3 Release Notes
===================

Now :meth:`dnf.Base.group_install` is able to exclude mandatory packages of the group from transaction.

===================
1.1.2 Release Notes
===================

Implemented :ref:`--downloadonly <downloadonly-label>` command line option.

Bugs fixed in 1.1.2:

* :rhbug:`1262082`
* :rhbug:`1250038`
* :rhbug:`1048433`
* :rhbug:`1259650`
* :rhbug:`1260198`
* :rhbug:`1259657`
* :rhbug:`1254982`
* :rhbug:`1261766`
* :rhbug:`1234491`
* :rhbug:`1256531`
* :rhbug:`1254687`
* :rhbug:`1261656`
* :rhbug:`1258364`

===================
1.1.1 Release Notes
===================

Implemented ``dnf mark`` :doc:`command <command_ref>`.

Bugs fixed in 1.1.1:

* :rhbug:`1249319`
* :rhbug:`1234763`
* :rhbug:`1242946`
* :rhbug:`1225225`
* :rhbug:`1254687`
* :rhbug:`1247766`
* :rhbug:`1125925`
* :rhbug:`1210289`

===================
1.1.0 Release Notes
===================

API additions in 1.1.0:

:meth:`dnf.Base.do_transaction` now accepts multiple displays.

Introduced ``install_weak_deps`` :doc:`configuration <conf_ref>` option.

Implemented ``strict`` :doc:`configuration <conf_ref>` option.

API deprecations in 1.1.0:

* ``dnf.callback.LoggingTransactionDisplay`` is deprecated now. It was considered part of API despite the fact that it has never been documented. Use :class:`dnf.callback.TransactionProgress` instead.

Bugs fixed in 1.1.0

* :rhbug:`1210445`
* :rhbug:`1218401`
* :rhbug:`1227952`
* :rhbug:`1197456`
* :rhbug:`1236310`
* :rhbug:`1219638`
* :rhbug:`1207981`
* :rhbug:`1208918`
* :rhbug:`1221635`
* :rhbug:`1236306`
* :rhbug:`1234639`
* :rhbug:`1244486`
* :rhbug:`1224248`
* :rhbug:`1243501`
* :rhbug:`1225237`

===================
1.0.2 Release Notes
===================

When a transaction is not successfully finished, DNF preserves downloaded packages
until the next successful transaction even if ``keepcache`` option is set to ``False``.

Maximum number of simultaneous package downloads can be adjusted by newly added
``max_parallel_downloads`` :doc:`configuration <conf_ref>` option.

``--repofrompath`` :doc:`command line argument <command_ref>` was introduced for temporary configuration of repositories.

API additions in 1.0.2:

Newly added package attributes: :attr:`dnf.package.Package.obsoletes`,
:attr:`dnf.package.Package.provides` and :attr:`dnf.package.Package.requires`.

:attr:`dnf.package.Query.filter`'s keys ``requires`` and ``provides`` now accepts
list of ``Hawkey.Reldep`` type.

Bugs fixed in 1.0.2:

* :rhbug:`1148630`
* :rhbug:`1176351`
* :rhbug:`1210445`
* :rhbug:`1173107`
* :rhbug:`1219199`
* :rhbug:`1220040`
* :rhbug:`1230975`
* :rhbug:`1232815`
* :rhbug:`1113384`
* :rhbug:`1133979`
* :rhbug:`1238958`
* :rhbug:`1238252`
* :rhbug:`1212320`

===================
1.0.1 Release Notes
===================

DNF follows the Semantic Versioning as defined at `<http://semver.org/>`_.

Documented SSL :doc:`configuration <conf_ref>` and :doc:`repository <api_repos>` options.

Added virtual provides allowing installation of DNF commands by their name in the form of
``dnf install dnf-command(name)``.

:doc:`dnf-automatic <automatic>` now by default waits random interval between 0 and 300 seconds before any network communication is performed.


Bugs fixed in 1.0.1:

* :rhbug:`1214968`
* :rhbug:`1222694`
* :rhbug:`1225246`
* :rhbug:`1213985`
* :rhbug:`1225277`
* :rhbug:`1223932`
* :rhbug:`1223614`
* :rhbug:`1203661`
* :rhbug:`1187741`

===================
1.0.0 Release Notes
===================

Improved documentation of YUM to DNF transition in :doc:`cli_vs_yum`.

:ref:`Auto remove command <autoremove_command-label>` does not remove `installonly` packages.

:ref:`Downgrade command <downgrade_command-label>` downgrades to specified package version if that is lower than currently installed one.

DNF now uses :attr:`dnf.repo.Repo.id` as a default value for :attr:`dnf.repo.Repo.name`.

Added support of repositories which use basic HTTP authentication.

API additions in 1.0.0:

:doc:`configuration <conf_ref>` options `username` and `password` (HTTP authentication)

:attr:`dnf.repo.Repo.username` and :attr:`dnf.repo.Repo.password` (HTTP authentication)

Bugs fixed in 1.0.0:

* :rhbug:`1215560`
* :rhbug:`1199648`
* :rhbug:`1208773`
* :rhbug:`1208018`
* :rhbug:`1207861`
* :rhbug:`1201445`
* :rhbug:`1210275`
* :rhbug:`1191275`
* :rhbug:`1207965`
* :rhbug:`1215289`

===================
0.6.5 Release Notes
===================

Python 3 version of DNF is now default in Fedora 23 and later.

yum-dnf package does not conflict with yum package.

`dnf erase` was deprecated in favor of `dnf remove`.

Extended documentation of handling non-existent packages and YUM to DNF transition in :doc:`cli_vs_yum`.

API additions in 0.6.5:

Newly added `pluginconfpath` option in :doc:`configuration <conf_ref>`.

Exposed `skip_if_unavailable` attribute from :doc:`api_repos`.

Documented `IOError` exception of method `fill_sack` from :class:`dnf.Base`.

Bugs fixed in 0.6.5:

* :rhbug:`1203151`
* :rhbug:`1187579`
* :rhbug:`1185977`
* :rhbug:`1195240`
* :rhbug:`1193914`
* :rhbug:`1195385`
* :rhbug:`1160806`
* :rhbug:`1186710`
* :rhbug:`1207726`
* :rhbug:`1157233`
* :rhbug:`1190671`
* :rhbug:`1191579`
* :rhbug:`1195325`
* :rhbug:`1154202`
* :rhbug:`1189083`
* :rhbug:`1193915`
* :rhbug:`1195661`
* :rhbug:`1190458`
* :rhbug:`1194685`
* :rhbug:`1160950`

===================
0.6.4 Release Notes
===================

Added example code snippets into :doc:`use_cases`.

Shows ordered groups/environments by `display_order` tag from :ref:`cli <grouplist_command-label>` and :doc:`api_comps` DNF API.

In commands the environment group is specified the same as :ref:`group <specifying_groups-label>`.

:ref:`skip_if_unavailable <skip_if_unavailable-label>` configuration option affects the metadata only.

added `enablegroups`, `minrate` and `timeout` :doc:`configuration options <conf_ref>`

API additions in 0.6.4:

Documented `install_set` and `remove_set attributes` from :doc:`api_transaction`.

Exposed `downloadsize`, `files`, `installsize` attributes from :doc:`api_package`.

Bugs fixed in 0.6.4:

* :rhbug:`1155877`
* :rhbug:`1175466`
* :rhbug:`1175466`
* :rhbug:`1186461`
* :rhbug:`1170156`
* :rhbug:`1184943`
* :rhbug:`1177002`
* :rhbug:`1169165`
* :rhbug:`1167982`
* :rhbug:`1157233`
* :rhbug:`1138096`
* :rhbug:`1181189`
* :rhbug:`1181397`
* :rhbug:`1175434`
* :rhbug:`1162887`
* :rhbug:`1156084`
* :rhbug:`1175098`
* :rhbug:`1174136`
* :rhbug:`1055910`
* :rhbug:`1155918`
* :rhbug:`1119030`
* :rhbug:`1177394`
* :rhbug:`1154476`

===================
0.6.3 Release Notes
===================

:ref:`Deltarpm <deltarpm-label>` configuration option is set on by default.

API additions in 0.6.3:

* dnf-automatic adds :ref:`motd emitter <emit_via_automatic-label>` as an alternative output

Bugs fixed in 0.6.3:

* :rhbug:`1153543`
* :rhbug:`1151231`
* :rhbug:`1163063`
* :rhbug:`1151854`
* :rhbug:`1151740`
* :rhbug:`1110780`
* :rhbug:`1149972`
* :rhbug:`1150474`
* :rhbug:`995537`
* :rhbug:`1149952`
* :rhbug:`1149350`
* :rhbug:`1170232`
* :rhbug:`1147523`
* :rhbug:`1148208`
* :rhbug:`1109927`

===================
0.6.2 Release Notes
===================

API additions in 0.6.2:

* Now :meth:`dnf.Base.package_install` method ignores already installed packages
* `CliError` exception from :mod:`dnf.cli` documented
* `Autoerase`, `History`, `Info`, `List`, `Provides`, `Repolist` commands do not force a sync of expired :ref:`metadata <metadata_synchronization-label>`
* `Install` command does installation only

Bugs fixed in 0.6.2:

* :rhbug:`909856`
* :rhbug:`1134893`
* :rhbug:`1138700`
* :rhbug:`1070902`
* :rhbug:`1124316`
* :rhbug:`1136584`
* :rhbug:`1135861`
* :rhbug:`1136223`
* :rhbug:`1122617`
* :rhbug:`1133830`
* :rhbug:`1121184`

===================
0.6.1 Release Notes
===================

New release adds :ref:`upgrade-type command <upgrade_type_automatic-label>` to `dnf-automatic` for choosing specific advisory type updates.

Implemented missing :ref:`history redo command <history_redo_command-label>` for repeating transactions.

Supports :ref:`gpgkey <repo_gpgkey-label>` repo config, :ref:`repo_gpgcheck <repo_gpgcheck-label>` and :ref:`gpgcheck <gpgcheck-label>` [main] and Repo configs.

Distributing new package :ref:`dnf-yum <dnf_yum_package-label>` that provides `/usr/bin/yum` as a symlink to `/usr/bin/dnf`.

API additions in 0.6.1:

* `exclude`, the third parameter of :meth:`dnf.Base.group_install` now also accepts glob patterns of package names.

Bugs fixed in 0.6.1:

* :rhbug:`1132335`
* :rhbug:`1071854`
* :rhbug:`1131969`
* :rhbug:`908764`
* :rhbug:`1130878`
* :rhbug:`1130432`
* :rhbug:`1118236`
* :rhbug:`1109915`

===================
0.6.0 Release Notes
===================

0.6.0 marks a new minor version of DNF and the first release to support advisories listing with the :ref:`udpateinfo command <updateinfo_command-label>`.

Support for the :ref:`include configuration directive <include-label>` has been added. Its functionality reflects Yum's ``includepkgs`` but it has been renamed to make it consistent with the ``exclude`` setting.

Group operations now produce a list of proposed marking changes to group objects and the user is given a chance to accept or reject them just like with an ordinary package transaction.

Bugs fixed in 0.6.0:

* :rhbug:`850912`
* :rhbug:`1055910`
* :rhbug:`1116666`
* :rhbug:`1118272`
* :rhbug:`1127206`

===================
0.5.5 Release Notes
===================

The full proxy configuration, API extensions and several bugfixes are provided in this release.

API changes in 0.5.5:

* `cachedir`, the second parameter of :meth:`dnf.repo.Repo.__init__` is not optional (the method has always been this way but the documentation was not matching)

API additions in 0.5.5:

* extended description and an example provided for :meth:`dnf.Base.fill_sack`
* :attr:`dnf.conf.Conf.proxy`
* :attr:`dnf.conf.Conf.proxy_username`
* :attr:`dnf.conf.Conf.proxy_password`
* :attr:`dnf.repo.Repo.proxy`
* :attr:`dnf.repo.Repo.proxy_username`
* :attr:`dnf.repo.Repo.proxy_password`

Bugs fixed in 0.5.5:

* :rhbug:`1100946`
* :rhbug:`1117789`
* :rhbug:`1120583`
* :rhbug:`1121280`
* :rhbug:`1122900`
* :rhbug:`1123688`

===================
0.5.4 Release Notes
===================

Several encodings bugs were fixed in this release, along with some packaging issues and updates to :doc:`conf_ref`.

Repository :ref:`priority <repo_priority-label>` configuration setting has been added, providing similar functionality to Yum Utils' Priorities plugin.

Bugs fixed in 0.5.4:

* :rhbug:`1048973`
* :rhbug:`1108908`
* :rhbug:`1116544`
* :rhbug:`1116839`
* :rhbug:`1116845`
* :rhbug:`1117102`
* :rhbug:`1117293`
* :rhbug:`1117678`
* :rhbug:`1118178`
* :rhbug:`1118796`
* :rhbug:`1119032`

===================
0.5.3 Release Notes
===================

A set of bugfixes related to i18n and Unicode handling. There is a ``-4/-6`` switch and a corresponding :ref:`ip_resolve <ip-resolve-label>` configuration option (both known from Yum) to force DNS resolving of hosts to IPv4 or IPv6 addresses.

0.5.3 comes with several extensions and clarifications in the API: notably :class:`~.dnf.transaction.Transaction` is introspectible now, :class:`Query.filter <dnf.query.Query.filter>` is more useful with new types of arguments and we've hopefully shed more light on how a client is expected to setup the configuration :attr:`~dnf.conf.Conf.substitutions`.

Finally, plugin authors can now use a new :meth:`~dnf.Plugin.resolved` hook.

API changes in 0.5.3:

* extended description given for :meth:`dnf.Base.fill_sack`
* :meth:`dnf.Base.select_group` has been dropped as announced in `0.4.18 Release Notes`_

API additions in 0.5.3:

* :attr:`dnf.conf.Conf.substitutions`
* :attr:`dnf.package.Package.arch`
* :attr:`dnf.package.Package.buildtime`
* :attr:`dnf.package.Package.epoch`
* :attr:`dnf.package.Package.installtime`
* :attr:`dnf.package.Package.name`
* :attr:`dnf.package.Package.release`
* :attr:`dnf.package.Package.sourcerpm`
* :attr:`dnf.package.Package.version`
* :meth:`dnf.Plugin.resolved`
* :meth:`dnf.query.Query.filter` accepts suffixes for its argument keys now which change the filter semantics.
* :mod:`dnf.rpm`
* :class:`dnf.transaction.TransactionItem`
* :class:`dnf.transaction.Transaction` is iterable now.

Bugs fixed in 0.5.3:

* :rhbug:`1047049`
* :rhbug:`1067156`
* :rhbug:`1093420`
* :rhbug:`1104757`
* :rhbug:`1105009`
* :rhbug:`1110800`
* :rhbug:`1111569`
* :rhbug:`1111997`
* :rhbug:`1112669`
* :rhbug:`1112704`

===================
0.5.2 Release Notes
===================

This release brings `autoremove command <https://bugzilla.redhat.com/show_bug.cgi?id=963345>`_ that removes any package that was originally installed as a dependency (e.g. had not been specified as an explicit argument to the install command) and is no longer needed.

Enforced verification of SSL connections can now be disabled with the :ref:`sslverify setting <sslverify-label>`.

We have been plagued with many crashes related to Unicode and encodings since the 0.5.0 release. These have been cleared out now.

There's more: improvement in startup time, `extended globbing semantics for input arguments <https://bugzilla.redhat.com/show_bug.cgi?id=1083679>`_ and `better search relevance sorting <https://bugzilla.redhat.com/show_bug.cgi?id=1093888>`_.

Bugs fixed in 0.5.2:

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

===================
0.5.1 Release Notes
===================

Bugfix release with several internal cleanups. One outstanding change for CLI users is that DNF is a lot less verbose now during the dependency resolving phase.

Bugs fixed in 0.5.1:

* :rhbug:`1065882`
* :rhbug:`1081753`
* :rhbug:`1089864`

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

* :meth:`dnf.Base.add_remote_rpms`
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

====================
0.4.19 Release Notes
====================

Arriving one week after 0.4.18, the 0.4.19 mainly provides a fix to a traceback in group operations under non-root users.

DNF starts to ship separate translation files (.mo) starting with this release.

Bugs fixed in 0.4.19:

* :rhbug:`1077173`
* :rhbug:`1078832`
* :rhbug:`1079621`

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
0.4.16 Release Notes
====================

The refactorings from 0.4.15 are introducing breakage causing the background ``dnf makecache`` runs traceback. This release fixes that.

Bugs fixed in 0.4.16:

* :rhbug:`1069996`

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
0.4.6 Release Notes
===================

0.4.6 brings two new major features. Firstly, it is the revival of ``history
undo``, so transactions can be reverted now.  Secondly, DNF will now limit the
number of installed kernels and *installonly* packages in general to the number
specified by :ref:`installonly_limit <installonly-limit-label>` configuration
option.

DNF now supports the ``group summary`` command and one-word group commands no
longer cause tracebacks, e.g. ``dnf grouplist``.

There are vast internal changes to ``dnf.cli``, the subpackage that provides CLI
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
0.4.5 Release Notes
===================

A serious bug causing `tracebacks during package downloads
<https://bugzilla.redhat.com/show_bug.cgi?id=1021087>`_ made it into 0.4.4 and
this release contains a fix for that. Also, a basic proxy support has been
readded now.

Bugs fixed in 0.4.5:

* :rhbug:`1021087`

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

===================
0.3.9 Release Notes
===================

This is a quick bugfix release dealing with reported bugs and tracebacks:

* :rhbug:`964584`
* :rhbug:`979942`
* :rhbug:`980227`
* :rhbug:`981310`

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
0.3.7 Release Notes
===================

This is a bugfix release:

* :rhbug:`916662`
* :rhbug:`967732`

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
0.3.3 Release Notes
===================

The improvements in 0.3.3 are only API changes to the logging. There is a new
module ``dnf.logging`` that defines simplified logging structure compared to
Yum, with fewer logging levels and `simpler usage for the developers
<https://github.com/rpm-software-management/dnf/wiki/Hacking#logging>`_. The RPM transaction logs are
no longer in ``/var/log/dnf.transaction.log`` but in ``/var/log/dnf.rpm.log`` by
default.

The exception classes were simplified and moved to ``dnf.exceptions``.

The following bugs are fixed in 0.3.3:

* :rhbug:`950722`
* :rhbug:`903775`

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
