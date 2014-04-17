# group.py
# Group CLI command.
#
# Copyright (C) 2012-2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals
from .. import commands
from dnf.i18n import _
from dnf.pycomp import unicode

import dnf.cli
import dnf.util
import itertools

def _ensure_grp_arg(cli, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one group for
    *basecmd* to act on.

    :param base: a :class:`dnf.Base` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        cli.logger.critical(_('Error: Need a group or list of groups'))
        commands._err_mini_usage(cli, basecmd)
        raise dnf.cli.CliError

class CompsQuery(object):

    AVAILABLE = 1
    INSTALLED = 2

    ENVIRONMENTS = 1
    GROUPS = 2

    def __init__(self, comps, prst, kinds, status):
        self.comps = comps
        self.prst = prst
        self.kinds = kinds
        self.status = status

    def _get(self, items, persistence_fn):
        lst = []
        for it in items:
            installed = persistence_fn(it.id).installed
            if self.status & self.INSTALLED and installed:
                lst.append(it)
            if self.status & self.AVAILABLE and not installed:
                lst.append(it)
        return lst

    def get(self, *patterns):
        res = dnf.util.Bunch()
        res.environments = []
        res.groups = []
        for pat in patterns:
            envs = grps = None
            if self.kinds & self.ENVIRONMENTS:
                envs = self._get(self.comps.environments_by_pattern(pat),
                                 self.prst.environment)
                res.environments.extend(envs)
            if self.kinds & self.GROUPS:
                grps = self._get(self.comps.groups_by_pattern(pat),
                                 self.prst.group)
                res.groups.extend(grps)
            if not envs and not grps:
                msg = _("No relevant match for the specified '%s'.")
                msg = msg % unicode(pat)
                raise dnf.cli.CliError(msg)
        return res

class GroupCommand(commands.Command):
    """ Single sub-command interface for most groups interaction. """

    direct_commands = {'grouplist'    : 'list',
                       'groupinstall' : 'install',
                       'groupupdate'  : 'install',
                       'groupremove'  : 'remove',
                       'grouperase'   : 'remove',
                       'groupinfo'    : 'info'}
    aliases = ('group', 'groups') + tuple(direct_commands.keys())
    summary = _("Display, or use, the groups information")
    usage = "[list|info|summary|install|upgrade|remove|mark] [%s]" % _('GROUP')

    def __init__(self, cli):
        super(GroupCommand, self).__init__(cli)

    def _grp_setup_doCommand(self):
        try:
            comps = self.base.read_comps()
        except dnf.exceptions.Error as e:
            return 1, [str(e)]
        if not comps:
            return 1, [_('No Groups Available in any repository')]

    @staticmethod
    def _split_extcmds(extcmds):
        if extcmds[0] == 'with-optional':
            types = tuple(dnf.const.GROUP_PACKAGE_TYPES + ('optional',))
            return types, extcmds[1:]
        return dnf.const.GROUP_PACKAGE_TYPES, extcmds

    def _grp_cmd(self, extcmds):
        return extcmds[0], extcmds[1:]

    _CMD_ALIASES = {'update'     : 'upgrade',
                    'erase'      : 'remove'}

    _MARK_CMDS = ('install', 'remove')

    def _install(self, extcmds):
        cnt = 0
        types, patterns = self._split_extcmds(extcmds)
        q = CompsQuery(self.base.comps, self.base.group_persistor,
                       CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS,
                       CompsQuery.AVAILABLE)
        res = q.get(*patterns)
        for env in res.environments:
            cnt += self.base.environment_install(env, types)
        for grp in res.groups:
            cnt += self.base.group_install(grp, types)
        if not cnt:
            msg = _('No packages in any requested groups available to install.')
            raise dnf.cli.CliError(msg)

    def _upgrade(self, patterns):
        q = CompsQuery(self.base.comps, self.base.group_persistor,
                       CompsQuery.GROUPS, CompsQuery.INSTALLED)
        res = q.get(*patterns)
        cnt = 0
        for grp in res.groups:
            cnt += self.base.group_upgrade(grp)
        if not cnt:
            msg = _('No packages marked for upgrade.')
            raise dnf.cli.CliError(msg)

    def _mark_install(self, patterns):
        q = CompsQuery(self.base.comps, self.base.group_persistor,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.AVAILABLE)
        solver = dnf.comps.Solver(self.base.group_persistor)
        res = q.get(*patterns)
        types = dnf.comps.DEFAULT | dnf.comps.MANDATORY | dnf.comps.OPTIONAL
        for env in res.environments:
            solver.environment_install(env, types, None)
        if res.environments:
            self.base.logger.info(_('Environments marked installed: %s') %
                                  ','.join([g.ui_name for g in res.environments]))
        for grp in res.groups:
            solver.group_install(grp, types, None)
        if res.groups:
            self.base.logger.info(_('Groups marked installed: %s') %
                                  ','.join([g.ui_name for g in res.groups]))

    def _mark_remove(self, patterns):
        q = CompsQuery(self.base.comps, self.base.group_persistor,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.INSTALLED)
        solver = dnf.comps.Solver(self.base.group_persistor)
        res = q.get(*patterns)
        for env in res.environments:
            solver.environment_remove(env)
        if res.environments:
            self.base.logger.info(_('Environments marked removed: %s') %
                                  ','.join([g.ui_name for g in res.environments]))
        for grp in res.groups:
            solver.group_remove(grp)
        if res.groups:
            self.base.logger.info(_('Groups marked removed: %s') %
                                  ','.join([g.ui_name for g in res.groups]))

    def _mark_subcmd(self, extcmds):
        if extcmds[0] in self._MARK_CMDS:
            return extcmds[0], extcmds[1:]
        return 'install', extcmds

    def _remove(self, patterns):
        cnt = 0
        q = CompsQuery(self.base.comps, self.base.group_persistor,
                       CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS,
                       CompsQuery.INSTALLED)
        res = q.get(*patterns)

        for env in res.environments:
            cnt += self.base.environment_remove(env)
        for grp in res.groups:
            cnt += self.base.group_remove(grp)
        if not cnt:
            raise dnf.cli.CliError(_('No packages to remove from given groups.'))

    @classmethod
    def canonical(cls, command_list):
        first = command_list[0]
        rest = command_list[1:]

        cmd = cls.direct_commands.get(first)
        if cmd is None:
            cmd = 'summary'
            if rest:
                cmd = rest.pop(0)
        cmd = cls._CMD_ALIASES.get(cmd, cmd)

        rest.insert(0, cmd)
        return ('groups', rest)

    def configure(self, extcmds):
        cmd = extcmds[0]
        demands = self.cli.demands
        demands.available_repos = True
        demands.sack_activation = True
        if cmd in ('install', 'mark', 'remove', 'upgrade'):
            demands.root_user = True

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        The exact conditions checked will vary depending on the
        subcommand that is being called.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        cmd, extcmds = self._grp_cmd(extcmds)

        commands.checkEnabledRepo(self.base)

        if cmd in ('install', 'remove', 'mark', 'info'):
            _ensure_grp_arg(self.cli, cmd, extcmds)

        if cmd in ('install', 'upgrade'):
            commands.checkGPGKey(self.base, self.cli)

        cmds = ('list', 'info', 'remove', 'install', 'upgrade', 'summary', 'mark')
        if cmd not in cmds:
            self.base.logger.critical(_('Invalid groups sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise dnf.cli.CliError

    def run(self, extcmds):
        cmd, extcmds = self._grp_cmd(extcmds)

        self._grp_setup_doCommand()

        if cmd == 'summary':
            return self.base.returnGroupSummary(extcmds)
        if cmd == 'list':
            return self.base.returnGroupLists(extcmds)
        if cmd == 'info':
            return self.base.returnGroupInfo(extcmds)
        if cmd == 'mark':
            (subcmd, extcmds) = self._mark_subcmd(extcmds)
            if subcmd == 'remove':
                return self._mark_remove(extcmds)
            else:
                assert subcmd == 'install'
                return self._mark_install(extcmds)

        self.cli.demands.resolving = True
        if cmd == 'install':
            return self._install(extcmds)
        if cmd == 'upgrade':
            return self._upgrade(extcmds)
        if cmd == 'remove':
            return self._remove(extcmds)
