# group.py
# Group CLI command.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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
from dnf.comps import CompsQuery
from dnf.cli import commands
from dnf.i18n import _, ucd

import dnf.cli
import dnf.exceptions
import dnf.util
import logging

logger = logging.getLogger("dnf")

class GroupCommand(commands.Command):
    """ Single sub-command interface for most groups interaction. """

    direct_commands = {'grouplist'    : 'list',
                       'groupinstall' : 'install',
                       'groupupdate'  : 'install',
                       'groupremove'  : 'remove',
                       'grouperase'   : 'remove',
                       'groupinfo'    : 'info'}
    aliases = ('group', 'groups', 'grp') + tuple(direct_commands.keys())
    summary = _('display, or use, the groups information')

    _CMD_ALIASES = {'update'     : 'upgrade',
                    'erase'      : 'remove'}
    _MARK_CMDS = ('install', 'remove')
    _GROUP_SUBCOMMANDS = ('summary', 'list', 'info', 'remove', 'install', 'upgrade', 'mark')


    def _canonical(self):
        # were we called with direct command?
        direct = self.direct_commands.get(self.opts.command)
        if direct:
            # canonize subcmd and args
            if self.opts.subcmd is not None:
                self.opts.args.insert(0, self.opts.subcmd)
            self.opts.subcmd = direct
        if self.opts.subcmd is None:
            self.opts.subcmd = 'summary'
        self.opts.subcmd = self._CMD_ALIASES.get(self.opts.subcmd,
                                                 self.opts.subcmd)

    def __init__(self, cli):
        super(GroupCommand, self).__init__(cli)
        self._remark = False

    def _assert_comps(self):
        msg = _('No group data available for configured repositories.')
        if not len(self.base.comps):
            raise dnf.exceptions.CompsError(msg)

    def _environment_lists(self, patterns):
        def available_pred(env):
            env_found = self.base.history.env.get(env.id)
            return not(env_found)

        self._assert_comps()
        if patterns is None:
            envs = self.base.comps.environments
        else:
            envs = self.base.comps.environments_by_pattern(",".join(patterns))

        return dnf.util.mapall(list, dnf.util.partition(available_pred, envs))

    def _group_lists(self, uservisible, patterns):
        def installed_pred(group):
            group_found = self.base.history.group.get(group.id)
            if group_found:
                return True
            return False
        installed = []
        available = []

        self._assert_comps()

        if patterns is None:
            grps = self.base.comps.groups
        else:
            grps = self.base.comps.groups_by_pattern(",".join(patterns))
        for grp in grps:
            tgt_list = available
            if installed_pred(grp):
                tgt_list = installed
            if not uservisible or grp.uservisible:
                tgt_list.append(grp)

        return installed, available

    def _grp_setup(self):
        self.base.read_comps(arch_filter=True)

    def _info(self, userlist):
        for strng in userlist:
            group_matched = False

            for env in self.base.comps.environments_by_pattern(strng):
                self.output.display_groups_in_environment(env)
                group_matched = True

            for group in self.base.comps.groups_by_pattern(strng):
                self.output.display_pkgs_in_groups(group)
                group_matched = True

            if not group_matched:
                logger.error(_('Warning: Group %s does not exist.'), strng)

        return 0, []

    def _list(self, userlist):
        uservisible = 1
        showinstalled = 0
        showavailable = 0
        print_ids = self.base.conf.verbose or self.opts.ids

        while userlist:
            if userlist[0] == 'hidden':
                uservisible = 0
                userlist.pop(0)
            elif userlist[0] == 'installed':
                showinstalled = 1
                userlist.pop(0)
            elif userlist[0] == 'available':
                showavailable = 1
                userlist.pop(0)
            elif userlist[0] == 'ids':
                print_ids = True
                userlist.pop(0)
            else:
                break
        if self.opts.hidden:
            uservisible = 0
        if self.opts.installed:
            showinstalled = 1
        if self.opts.available:
            showavailable = 1
        if not userlist:
            userlist = None # Match everything...

        errs = False
        if userlist is not None:
            for group in userlist:
                comps = self.base.comps
                in_group = len(comps.groups_by_pattern(group)) > 0
                in_environment = len(comps.environments_by_pattern(group)) > 0
                if not in_group and not in_environment:
                    logger.error(_('Warning: No groups match:') + '\n   %s',
                                 group)
                    errs = True
            if errs:
                return 0, []

        env_inst, env_avail = self._environment_lists(userlist)
        installed, available = self._group_lists(uservisible, userlist)

        def _out_grp(sect, group):
            if not done:
                print(sect)
            msg = '   %s' % group.ui_name
            if print_ids:
                msg += ' (%s)' % group.id
            if group.lang_only:
                msg += ' [%s]' % group.lang_only
            print('{}'.format(msg))

        def _out_env(sect, envs):
            if envs:
                print(sect)
            for e in envs:
                msg = '   %s' % e.ui_name
                if print_ids:
                    msg += ' (%s)' % e.id
                print(msg)

        if not showinstalled:
            _out_env(_('Available Environment Groups:'), env_avail)
        if not showavailable:
            _out_env(_('Installed Environment Groups:'), env_inst)

        if not showavailable:
            done = False
            for group in installed:
                if group.lang_only:
                    continue
                _out_grp(_('Installed Groups:'), group)
                done = True

            done = False
            for group in installed:
                if not group.lang_only:
                    continue
                _out_grp(_('Installed Language Groups:'), group)
                done = True

        if showinstalled:
            return 0, []

        done = False
        for group in available:
            if group.lang_only:
                continue
            _out_grp(_('Available Groups:'), group)
            done = True

        done = False
        for group in available:
            if not group.lang_only:
                continue
            _out_grp(_('Available Language Groups:'), group)
            done = True

        return 0, []

    def _mark_install(self, patterns):
        q = CompsQuery(self.base.comps, self.base.history,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.AVAILABLE | CompsQuery.INSTALLED)
        solver = self.base._build_comps_solver()
        res = q.get(*patterns)

        if self.opts.with_optional:
            types = tuple(self.base.conf.group_package_types + ['optional'])
        else:
            types = tuple(self.base.conf.group_package_types)
        pkg_types = self.base._translate_comps_pkg_types(types)
        for env_id in res.environments:
            dnf.comps.install_or_skip(solver._environment_install, env_id, pkg_types)
        for group_id in res.groups:
            dnf.comps.install_or_skip(solver._group_install, group_id, pkg_types)

    def _mark_remove(self, patterns):
        q = CompsQuery(self.base.comps, self.base.history,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.INSTALLED)
        solver = self.base._build_comps_solver()
        res = q.get(*patterns)
        for env_id in res.environments:
            assert dnf.util.is_string_type(env_id)
            solver._environment_remove(env_id)
        for grp_id in res.groups:
            assert dnf.util.is_string_type(grp_id)
            solver._group_remove(grp_id)

    def _mark_subcmd(self, extcmds):
        if extcmds[0] in self._MARK_CMDS:
            return extcmds[0], extcmds[1:]
        return 'install', extcmds

    def _summary(self, userlist):
        uservisible = 1
        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible = 0
                userlist.pop(0)
        if self.opts.hidden:
            uservisible = 0
        if not userlist:
            userlist = None # Match everything...

        installed, available = self._group_lists(uservisible, userlist)

        def _out_grp(sect, num):
            if not num:
                return
            logger.info('%s %u', sect, num)
        done = 0
        for group in installed:
            if group.lang_only:
                continue
            done += 1
        _out_grp(_('Installed Groups:'), done)

        done = 0
        for group in installed:
            if not group.lang_only:
                continue
            done += 1
        _out_grp(_('Installed Language Groups:'), done)

        done = False
        for group in available:
            if group.lang_only:
                continue
            done += 1
        _out_grp(_('Available Groups:'), done)

        done = False
        for group in available:
            if not group.lang_only:
                continue
            done += 1
        _out_grp(_('Available Language Groups:'), done)

        return 0, []

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('--with-optional', action='store_true',
                            help=_("include optional packages from group"))
        grpparser = parser.add_mutually_exclusive_group()
        grpparser.add_argument('--hidden', action='store_true',
                               help=_("show also hidden groups"))
        grpparser.add_argument('--installed', action='store_true',
                               help=_("show only installed groups"))
        grpparser.add_argument('--available', action='store_true',
                               help=_("show only available groups"))
        grpparser.add_argument('--ids', action='store_true',
                               help=_("show also ID of groups"))
        parser.add_argument('subcmd', nargs='?', metavar='COMMAND',
                            help=_('available subcommands: {} (default), {}').format(
                                GroupCommand._GROUP_SUBCOMMANDS[0],
                                ', '.join(GroupCommand._GROUP_SUBCOMMANDS[1:])))
        parser.add_argument('args', nargs='*', metavar='COMMAND_ARG',
                            help=_('argument for group subcommand'))

    def configure(self):
        self._canonical()

        cmd = self.opts.subcmd
        args = self.opts.args

        if cmd not in self._GROUP_SUBCOMMANDS:
            logger.critical(_('Invalid groups sub-command, use: %s.'),
                            ", ".join(self._GROUP_SUBCOMMANDS))
            raise dnf.cli.CliError
        if cmd in ('install', 'remove', 'mark', 'info') and not args:
            self.cli.optparser.print_help(self)
            raise dnf.cli.CliError

        demands = self.cli.demands
        demands.sack_activation = True
        if cmd in ('install', 'mark', 'remove', 'upgrade'):
            demands.root_user = True
            demands.resolving = True
        if cmd == 'remove':
            demands.allow_erasing = True
            demands.available_repos = False
        else:
            demands.available_repos = True

        commands._checkEnabledRepo(self.base)

        if cmd in ('install', 'upgrade'):
            commands._checkGPGKey(self.base, self.cli)

    def run(self):
        cmd = self.opts.subcmd
        extcmds = self.opts.args

        self._grp_setup()

        if cmd == 'summary':
            return self._summary(extcmds)
        if cmd == 'list':
            return self._list(extcmds)
        if cmd == 'info':
            return self._info(extcmds)
        if cmd == 'mark':
            (subcmd, extcmds) = self._mark_subcmd(extcmds)
            if subcmd == 'remove':
                return self._mark_remove(extcmds)
            else:
                assert subcmd == 'install'
                return self._mark_install(extcmds)

        if cmd == 'install':
            if self.opts.with_optional:
                types = tuple(self.base.conf.group_package_types + ['optional'])
            else:
                types = tuple(self.base.conf.group_package_types)

            self._remark = True
            try:
                return self.base.env_group_install(extcmds, types,
                                                   self.base.conf.strict)
            except dnf.exceptions.MarkingError as e:
                msg = _('No package %s available.')
                logger.info(msg, self.base.output.term.bold(e))
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Unable to find a mandatory group package."))
        if cmd == 'upgrade':
            return self.base.env_group_upgrade(extcmds)
        if cmd == 'remove':
            for arg in extcmds:
                try:
                    self.base.env_group_remove([arg])
                except dnf.exceptions.Error:
                    pass

    def run_transaction(self):
        if not self._remark:
            return
        goal = self.base._goal
        history = self.base.history
        names = goal.group_members
        for pkg in self.base.sack.query().installed().filterm(name=names):
            reason = history.rpm.get_reason(pkg)
            history.set_reason(pkg, goal.group_reason(pkg, reason))
