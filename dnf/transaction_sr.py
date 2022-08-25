# Copyright (C) 2020 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import libdnf
import hawkey

from dnf.i18n import _
import dnf.exceptions

import json


VERSION_MAJOR = 0
VERSION_MINOR = 0
VERSION = "%s.%s" % (VERSION_MAJOR, VERSION_MINOR)
"""
The version of the stored transaction.

MAJOR version denotes backwards incompatible changes (old dnf won't work with
new transaction JSON).

MINOR version denotes extending the format without breaking backwards
compatibility (old dnf can work with new transaction JSON). Forwards
compatibility needs to be handled by being able to process the old format as
well as the new one.
"""


class TransactionError(dnf.exceptions.Error):
    def __init__(self, msg):
        super(TransactionError, self).__init__(msg)


class TransactionReplayError(dnf.exceptions.Error):
    def __init__(self, filename, errors):
        """
        :param filename: The name of the transaction file being replayed
        :param errors: a list of error classes or a string with an error description
        """

        # store args in case someone wants to read them from a caught exception
        self.filename = filename
        if isinstance(errors, (list, tuple)):
            self.errors = errors
        else:
            self.errors = [errors]

        if filename:
            msg = _('The following problems occurred while replaying the transaction from file "{filename}":').format(filename=filename)
        else:
            msg = _('The following problems occurred while running a transaction:')

        for error in self.errors:
            msg += "\n  " + str(error)

        super(TransactionReplayError, self).__init__(msg)


class IncompatibleTransactionVersionError(TransactionReplayError):
    def __init__(self, filename, msg):
        super(IncompatibleTransactionVersionError, self).__init__(filename, msg)


def _check_version(version, filename):
    major, minor = version.split('.')

    try:
        major = int(major)
    except ValueError as e:
        raise TransactionReplayError(
            filename,
            _('Invalid major version "{major}", number expected.').format(major=major)
        )

    try:
        int(minor)  # minor is unused, just check it's a number
    except ValueError as e:
        raise TransactionReplayError(
            filename,
            _('Invalid minor version "{minor}", number expected.').format(minor=minor)
        )

    if major != VERSION_MAJOR:
        raise IncompatibleTransactionVersionError(
            filename,
            _('Incompatible major version "{major}", supported major version is "{major_supp}".')
                .format(major=major, major_supp=VERSION_MAJOR)
        )


def serialize_transaction(transaction):
    """
    Serializes a transaction to a data structure that is equivalent to the stored JSON format.
    :param transaction: the transaction to serialize (an instance of dnf.db.history.TransactionWrapper)
    """

    data = {
        "version": VERSION,
    }
    rpms = []
    groups = []
    environments = []

    if transaction is None:
        return data

    for tsi in transaction.packages():
        if tsi.is_package():
            rpms.append({
                "action": tsi.action_name,
                "nevra": tsi.nevra,
                "reason": libdnf.transaction.TransactionItemReasonToString(tsi.reason),
                "repo_id": tsi.from_repo
            })

        elif tsi.is_group():
            group = tsi.get_group()

            group_data = {
                "action": tsi.action_name,
                "id": group.getGroupId(),
                "packages": [],
                "package_types": libdnf.transaction.compsPackageTypeToString(group.getPackageTypes())
            }

            for pkg in group.getPackages():
                group_data["packages"].append({
                    "name": pkg.getName(),
                    "installed": pkg.getInstalled(),
                    "package_type": libdnf.transaction.compsPackageTypeToString(pkg.getPackageType())
                })

            groups.append(group_data)

        elif tsi.is_environment():
            env = tsi.get_environment()

            env_data = {
                "action": tsi.action_name,
                "id": env.getEnvironmentId(),
                "groups": [],
                "package_types": libdnf.transaction.compsPackageTypeToString(env.getPackageTypes())
            }

            for grp in env.getGroups():
                env_data["groups"].append({
                    "id": grp.getGroupId(),
                    "installed": grp.getInstalled(),
                    "group_type": libdnf.transaction.compsPackageTypeToString(grp.getGroupType())
                })

            environments.append(env_data)

    if rpms:
        data["rpms"] = rpms

    if groups:
        data["groups"] = groups

    if environments:
        data["environments"] = environments

    return data


class TransactionReplay(object):
    """
    A class that encapsulates replaying a transaction. The transaction data are
    loaded and stored when the class is initialized. The transaction is run by
    calling the `run()` method, after the transaction is created (but before it is
    performed), the `post_transaction()` method needs to be called to verify no
    extra packages were pulled in and also to fix the reasons.
    """

    def __init__(
        self,
        base,
        filename="",
        data=None,
        ignore_extras=False,
        ignore_installed=False,
        skip_unavailable=False
    ):
        """
        :param base: the dnf base
        :param filename: the filename to load the transaction from (conflicts with the 'data' argument)
        :param data: the dictionary to load the transaction from (conflicts with the 'filename' argument)
        :param ignore_extras: whether to ignore extra package pulled into the transaction
        :param ignore_installed: whether to ignore installed versions of packages
        :param skip_unavailable: whether to skip transaction packages that aren't available
        """

        self._base = base
        self._filename = filename
        self._ignore_installed = ignore_installed
        self._ignore_extras = ignore_extras
        self._skip_unavailable = skip_unavailable

        if not self._base.conf.strict:
            self._skip_unavailable = True

        self._nevra_cache = set()
        self._nevra_reason_cache = {}
        self._warnings = []

        if filename and data:
            raise ValueError(_("Conflicting TransactionReplay arguments have been specified: filename, data"))
        elif filename:
            self._load_from_file(filename)
        else:
            self._load_from_data(data)


    def _load_from_file(self, fn):
        self._filename = fn
        with open(fn, "r") as f:
            try:
                replay_data = json.load(f)
            except json.decoder.JSONDecodeError as e:
                raise TransactionReplayError(fn, str(e) + ".")

        try:
            self._load_from_data(replay_data)
        except TransactionError as e:
            raise TransactionReplayError(fn, e)

    def _load_from_data(self, data):
        self._replay_data = data
        self._verify_toplevel_json(self._replay_data)

        self._rpms = self._replay_data.get("rpms", [])
        self._assert_type(self._rpms, list, "rpms", "array")

        self._groups = self._replay_data.get("groups", [])
        self._assert_type(self._groups, list, "groups", "array")

        self._environments = self._replay_data.get("environments", [])
        self._assert_type(self._environments, list, "environments", "array")

    def _raise_or_warn(self, warn_only, msg):
        if warn_only:
            self._warnings.append(msg)
        else:
            raise TransactionError(msg)

    def _assert_type(self, value, t, id, expected):
        if not isinstance(value, t):
            raise TransactionError(_('Unexpected type of "{id}", {exp} expected.').format(id=id, exp=expected))

    def _verify_toplevel_json(self, replay_data):
        fn = self._filename

        if "version" not in replay_data:
            raise TransactionReplayError(fn, _('Missing key "{key}".'.format(key="version")))

        self._assert_type(replay_data["version"], str, "version", "string")

        _check_version(replay_data["version"], fn)

    def _replay_pkg_action(self, pkg_data):
        try:
            action = pkg_data["action"]
            nevra = pkg_data["nevra"]
            repo_id = pkg_data["repo_id"]
            reason = libdnf.transaction.StringToTransactionItemReason(pkg_data["reason"])
        except KeyError as e:
            raise TransactionError(
                _('Missing object key "{key}" in an rpm.').format(key=e.args[0])
            )
        except IndexError as e:
            raise TransactionError(
                _('Unexpected value of package reason "{reason}" for rpm nevra "{nevra}".')
                    .format(reason=pkg_data["reason"], nevra=nevra)
            )

        subj = hawkey.Subject(nevra)
        parsed_nevras = subj.get_nevra_possibilities(forms=[hawkey.FORM_NEVRA])

        if len(parsed_nevras) != 1:
            raise TransactionError(_('Cannot parse NEVRA for package "{nevra}".').format(nevra=nevra))

        parsed_nevra = parsed_nevras[0]
        na = "%s.%s" % (parsed_nevra.name, parsed_nevra.arch)

        query_na = self._base.sack.query().filter(name=parsed_nevra.name, arch=parsed_nevra.arch)

        epoch = parsed_nevra.epoch if parsed_nevra.epoch is not None else 0
        query = query_na.filter(epoch=epoch, version=parsed_nevra.version, release=parsed_nevra.release)

        # In case the package is found in the same repo as in the original
        # transaction, limit the query to that plus installed packages. IOW
        # remove packages with the same NEVRA in case they are found in
        # multiple repos and the repo the package came from originally is one
        # of them.
        # This can e.g. make a difference in the system-upgrade plugin, in case
        # the same NEVRA is in two repos, this makes sure the same repo is used
        # for both download and upgrade steps of the plugin.
        if repo_id:
            query_repo = query.filter(reponame=repo_id)
            if query_repo:
                query = query_repo.union(query.installed())

        if not query:
            self._raise_or_warn(self._skip_unavailable, _('Cannot find rpm nevra "{nevra}".').format(nevra=nevra))
            return

        # a cache to check no extra packages were pulled into the transaction
        if action != "Reason Change":
            self._nevra_cache.add(nevra)

        # store reasons for forward actions and "Removed", the rest of the
        # actions reasons should stay as they were determined by the transaction
        if action in ("Install", "Upgrade", "Downgrade", "Reinstall", "Removed"):
            self._nevra_reason_cache[nevra] = reason

        if action in ("Install", "Upgrade", "Downgrade"):
            if action == "Install" and query_na.installed() and not self._base._get_installonly_query(query_na):
                self._raise_or_warn(self._ignore_installed,
                    _('Package "{na}" is already installed for action "{action}".').format(na=na, action=action))

            sltr = dnf.selector.Selector(self._base.sack).set(pkg=query)
            self._base.goal.install(select=sltr, optional=not self._base.conf.strict)
        elif action == "Reinstall":
            query = query.available()

            if not query:
                self._raise_or_warn(self._skip_unavailable,
                    _('Package nevra "{nevra}" not available in repositories for action "{action}".')
                    .format(nevra=nevra, action=action))
                return

            sltr = dnf.selector.Selector(self._base.sack).set(pkg=query)
            self._base.goal.install(select=sltr, optional=not self._base.conf.strict)
        elif action in ("Upgraded", "Downgraded", "Reinstalled", "Removed", "Obsoleted"):
            query = query.installed()

            if not query:
                self._raise_or_warn(self._ignore_installed,
                    _('Package nevra "{nevra}" not installed for action "{action}".').format(nevra=nevra, action=action))
                return

            # erasing the original version (the reverse part of an action like
            # e.g. upgrade) is more robust, but we can't do it if
            # skip_unavailable is True, because if the forward part of the
            # action is skipped, we would simply remove the package here
            if not self._skip_unavailable or action == "Removed":
                for pkg in query:
                    self._base.goal.erase(pkg, clean_deps=False)
        elif action == "Reason Change":
            self._base.history.set_reason(query[0], reason)
        else:
            raise TransactionError(
                _('Unexpected value of package action "{action}" for rpm nevra "{nevra}".')
                    .format(action=action, nevra=nevra)
            )

    def _create_swdb_group(self, group_id, pkg_types, pkgs):
        comps_group = self._base.comps._group_by_id(group_id)
        if not comps_group:
            self._raise_or_warn(self._skip_unavailable, _("Group id '%s' is not available.") % group_id)
            return None

        swdb_group = self._base.history.group.new(group_id, comps_group.name, comps_group.ui_name, pkg_types)

        try:
            for pkg in pkgs:
                name = pkg["name"]
                self._assert_type(name, str, "groups.packages.name", "string")
                installed = pkg["installed"]
                self._assert_type(installed, bool, "groups.packages.installed", "boolean")
                package_type = pkg["package_type"]
                self._assert_type(package_type, str, "groups.packages.package_type", "string")

                try:
                    swdb_group.addPackage(name, installed, libdnf.transaction.stringToCompsPackageType(package_type))
                except libdnf.error.Error as e:
                    raise TransactionError(str(e))

        except KeyError as e:
            raise TransactionError(
                _('Missing object key "{key}" in groups.packages.').format(key=e.args[0])
            )

        return swdb_group

    def _swdb_group_install(self, group_id, pkg_types, pkgs):
        swdb_group = self._create_swdb_group(group_id, pkg_types, pkgs)

        if swdb_group is not None:
            self._base.history.group.install(swdb_group)

    def _swdb_group_upgrade(self, group_id, pkg_types, pkgs):
        if not self._base.history.group.get(group_id):
            self._raise_or_warn( self._ignore_installed, _("Group id '%s' is not installed.") % group_id)
            return

        swdb_group = self._create_swdb_group(group_id, pkg_types, pkgs)

        if swdb_group is not None:
            self._base.history.group.upgrade(swdb_group)

    def _swdb_group_downgrade(self, group_id, pkg_types, pkgs):
        if not self._base.history.group.get(group_id):
            self._raise_or_warn(self._ignore_installed, _("Group id '%s' is not installed.") % group_id)
            return

        swdb_group = self._create_swdb_group(group_id, pkg_types, pkgs)

        if swdb_group is not None:
            self._base.history.group.downgrade(swdb_group)

    def _swdb_group_remove(self, group_id, pkg_types, pkgs):
        if not self._base.history.group.get(group_id):
            self._raise_or_warn(self._ignore_installed, _("Group id '%s' is not installed.") % group_id)
            return

        swdb_group = self._create_swdb_group(group_id, pkg_types, pkgs)

        if swdb_group is not None:
            self._base.history.group.remove(swdb_group)

    def _create_swdb_environment(self, env_id, pkg_types, groups):
        comps_env = self._base.comps._environment_by_id(env_id)
        if not comps_env:
            self._raise_or_warn(self._skip_unavailable, _("Environment id '%s' is not available.") % env_id)
            return None

        swdb_env = self._base.history.env.new(env_id, comps_env.name, comps_env.ui_name, pkg_types)

        try:
            for grp in groups:
                id = grp["id"]
                self._assert_type(id, str, "environments.groups.id", "string")
                installed = grp["installed"]
                self._assert_type(installed, bool, "environments.groups.installed", "boolean")
                group_type = grp["group_type"]
                self._assert_type(group_type, str, "environments.groups.group_type", "string")

                try:
                    group_type = libdnf.transaction.stringToCompsPackageType(group_type)
                except libdnf.error.Error as e:
                    raise TransactionError(str(e))

                if group_type not in (
                    libdnf.transaction.CompsPackageType_MANDATORY,
                    libdnf.transaction.CompsPackageType_OPTIONAL
                ):
                    raise TransactionError(
                        _('Invalid value "{group_type}" of environments.groups.group_type, '
                            'only "mandatory" or "optional" is supported.'
                        ).format(group_type=grp["group_type"])
                    )

                swdb_env.addGroup(id, installed, group_type)
        except KeyError as e:
            raise TransactionError(
                _('Missing object key "{key}" in environments.groups.').format(key=e.args[0])
            )

        return swdb_env

    def _swdb_environment_install(self, env_id, pkg_types, groups):
        swdb_env = self._create_swdb_environment(env_id, pkg_types, groups)

        if swdb_env is not None:
            self._base.history.env.install(swdb_env)

    def _swdb_environment_upgrade(self, env_id, pkg_types, groups):
        if not self._base.history.env.get(env_id):
            self._raise_or_warn(self._ignore_installed,_("Environment id '%s' is not installed.") % env_id)
            return

        swdb_env = self._create_swdb_environment(env_id, pkg_types, groups)

        if swdb_env is not None:
            self._base.history.env.upgrade(swdb_env)

    def _swdb_environment_downgrade(self, env_id, pkg_types, groups):
        if not self._base.history.env.get(env_id):
            self._raise_or_warn(self._ignore_installed, _("Environment id '%s' is not installed.") % env_id)
            return

        swdb_env = self._create_swdb_environment(env_id, pkg_types, groups)

        if swdb_env is not None:
            self._base.history.env.downgrade(swdb_env)

    def _swdb_environment_remove(self, env_id, pkg_types, groups):
        if not self._base.history.env.get(env_id):
            self._raise_or_warn(self._ignore_installed, _("Environment id '%s' is not installed.") % env_id)
            return

        swdb_env = self._create_swdb_environment(env_id, pkg_types, groups)

        if swdb_env is not None:
            self._base.history.env.remove(swdb_env)

    def get_data(self):
        """
        :returns: the loaded data of the transaction
        """

        return self._replay_data

    def get_warnings(self):
        """
        :returns: an array of warnings gathered during the transaction replay
        """

        return self._warnings

    def run(self):
        """
        Replays the transaction.
        """

        fn = self._filename
        errors = []

        for pkg_data in self._rpms:
            try:
                self._replay_pkg_action(pkg_data)
            except TransactionError as e:
                errors.append(e)

        for group_data in self._groups:
            try:
                action = group_data["action"]
                group_id = group_data["id"]

                try:
                    pkg_types = libdnf.transaction.stringToCompsPackageType(group_data["package_types"])
                except libdnf.error.Error as e:
                    errors.append(TransactionError(str(e)))
                    continue

                if action == "Install":
                    self._swdb_group_install(group_id, pkg_types, group_data["packages"])
                elif action == "Upgrade":
                    self._swdb_group_upgrade(group_id, pkg_types, group_data["packages"])
                elif action == "Downgraded":
                    self._swdb_group_downgrade(group_id, pkg_types, group_data["packages"])
                elif action == "Removed":
                    self._swdb_group_remove(group_id, pkg_types, group_data["packages"])
                else:
                    errors.append(TransactionError(
                        _('Unexpected value of group action "{action}" for group "{group}".')
                            .format(action=action, group=group_id)
                    ))
            except KeyError as e:
                errors.append(TransactionError(
                    _('Missing object key "{key}" in a group.').format(key=e.args[0])
                ))
            except TransactionError as e:
                errors.append(e)

        for env_data in self._environments:
            try:
                action = env_data["action"]
                env_id = env_data["id"]

                try:
                    pkg_types = libdnf.transaction.stringToCompsPackageType(env_data["package_types"])
                except libdnf.error.Error as e:
                    errors.append(TransactionError(str(e)))
                    continue

                if action == "Install":
                    self._swdb_environment_install(env_id, pkg_types, env_data["groups"])
                elif action == "Upgrade":
                    self._swdb_environment_upgrade(env_id, pkg_types, env_data["groups"])
                elif action == "Downgraded":
                    self._swdb_environment_downgrade(env_id, pkg_types, env_data["groups"])
                elif action == "Removed":
                    self._swdb_environment_remove(env_id, pkg_types, env_data["groups"])
                else:
                    errors.append(TransactionError(
                        _('Unexpected value of environment action "{action}" for environment "{env}".')
                            .format(action=action, env=env_id)
                    ))
            except KeyError as e:
                errors.append(TransactionError(
                    _('Missing object key "{key}" in an environment.').format(key=e.args[0])
                ))
            except TransactionError as e:
                errors.append(e)

        if errors:
            raise TransactionReplayError(fn, errors)

    def post_transaction(self):
        """
        Sets reasons in the transaction history to values from the stored transaction.

        Also serves to check whether additional packages were pulled in by the
        transaction, which results in an error (unless ignore_extras is True).
        """

        if not self._base.transaction:
            return

        errors = []

        for tsi in self._base.transaction:
            try:
                pkg = tsi.pkg
            except KeyError as e:
                # the transaction item has no package, happens for action == "Reason Change"
                continue

            nevra = str(pkg)

            if nevra not in self._nevra_cache:
                # if ignore_installed is True, we don't want to check for
                # Upgraded/Downgraded/Reinstalled extras in the transaction,
                # basically those may be installed and we are ignoring them
                if not self._ignore_installed or not tsi.action in (
                    libdnf.transaction.TransactionItemAction_UPGRADED,
                    libdnf.transaction.TransactionItemAction_DOWNGRADED,
                    libdnf.transaction.TransactionItemAction_REINSTALLED
                ):
                    msg = _('Package nevra "{nevra}", which is not present in the transaction file, was pulled '
                        'into the transaction.'
                    ).format(nevra=nevra)

                    if not self._ignore_extras:
                        errors.append(TransactionError(msg))
                    else:
                        self._warnings.append(msg)

            try:
                replay_reason = self._nevra_reason_cache[nevra]

                if tsi.action in (
                    libdnf.transaction.TransactionItemAction_INSTALL,
                    libdnf.transaction.TransactionItemAction_REMOVE
                ) or libdnf.transaction.TransactionItemReasonCompare(replay_reason, tsi.reason) > 0:
                    tsi.reason = replay_reason
            except KeyError as e:
                # if the pkg nevra wasn't found, we don't want to change the reason
                pass

        if errors:
            raise TransactionReplayError(self._filename, errors)
