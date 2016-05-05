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
from dnf.i18n import _

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
    aliases = ('group', 'groups') + tuple(direct_commands.keys())
    summary = _('display, or use, the groups information')
    usage = "[list|info|summary|install|upgrade|remove|mark] [%s]" % _('GROUP')

    _CMD_ALIASES = {'update'     : 'upgrade',
                    'erase'      : 'remove'}
    _MARK_CMDS = ('install', 'remove')


    @staticmethod
    def _split_extcmds(extcmds):
        if extcmds[0] == 'with-optional':
            types = tuple(dnf.const.GROUP_PACKAGE_TYPES + ('optional',))
            return types, extcmds[1:]
        return dnf.const.GROUP_PACKAGE_TYPES, extcmds

    def _canonical(self):
        # were we called with direct command?
        direct = self.direct_commands.get(self.opts.command[0])
        if direct:
            # canonize subcmd and args
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
            return not self.base._group_persistor.environment(env.id).installed

        self._assert_comps()
        if patterns is None:
            envs = self.base.comps.environments
        else:
            envs = self.base.comps.environments_by_pattern(",".join(patterns))

        return dnf.util.mapall(list, dnf.util.partition(available_pred, envs))

    def _group_lists(self, uservisible, patterns):
        def installed_pred(group):
            return self.base._group_persistor.group(group.id).installed
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
        comps = self.base.read_comps()

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
        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible = 0
                userlist.pop(0)
            elif userlist[0] == 'installed':
                showinstalled = 1
                userlist.pop(0)
            elif userlist[0] == 'available':
                showavailable = 1
                userlist.pop(0)

        if not userlist:
            userlist = None # Match everything...

        errs = False
        if userlist is not None:
            for group in userlist:
                in_group = len(self.base.comps.groups_by_pattern(group)) > 0
                in_environment = len(self.base.comps.environments_by_pattern(group)) > 0
                if not in_group and not in_environment:
                    logger.error(_('Warning: No groups match:') + '\n   %s', group)
                    errs = True
            if errs:
                return 0, []

        env_inst, env_avail = self._environment_lists(userlist)
        installed, available = self._group_lists(uservisible, userlist)

        def _out_grp(sect, group):
            if not done:
                logger.info(sect)
            msg = '   %s' % group.ui_name
            if self.base.conf.verbose:
                msg += ' (%s)' % group.id
            if group.lang_only:
                msg += ' [%s]' % group.lang_only
            logger.info('%s', msg)

        def _out_env(sect, envs):
            if envs:
                logger.info(sect)
            for e in envs:
                msg = '   %s' % e.ui_name
                if self.base.conf.verbose:
                    msg += ' (%s)' % e.id
                logger.info(msg)

        if not showinstalled:
            _out_env(_('Available environment groups:'), env_avail)
        if not showavailable:
            _out_env(_('Installed environment groups:'), env_inst)

        if not showavailable:
            done = False
            for group in installed:
                if group.lang_only:
                    continue
                _out_grp(_('Installed groups:'), group)
                done = True

            done = False
            for group in installed:
                if not group.lang_only:
                    continue
                _out_grp(_('Installed language groups:'), group)
                done = True

        if showinstalled:
            return 0, []

        done = False
        for group in available:
            if group.lang_only:
                continue
            _out_grp(_('Available groups:'), group)
            done = True

        done = False
        for group in available:
            if not group.lang_only:
                continue
            _out_grp(_('Available language groups:'), group)
            done = True

        return 0, []

    def _mark_install(self, patterns):
        prst = self.base._group_persistor
        q = CompsQuery(self.base.comps, prst,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.AVAILABLE | CompsQuery.INSTALLED)
        solver = self.base._build_comps_solver()
        res = q.get(*patterns)
        types = dnf.comps.DEFAULT | dnf.comps.MANDATORY | dnf.comps.OPTIONAL

        for env_id in res.environments:
            if not dnf.comps.install_or_skip(solver.environment_install,
                                             env_id, types):
                res.environments.remove(env_id)
        for group_id in res.groups:
            if not dnf.comps.install_or_skip(solver.group_install,
                                             group_id, types):
                res.groups.remove(group_id)

        if res.environments:
            logger.info(_('Environments marked installed: %s'),
                        ','.join([prst.environment(g).ui_name
                                  for g in res.environments]))
        if res.groups:
            logger.info(_('Groups marked installed: %s'),
                        ','.join([prst.group(g).ui_name for g in res.groups]))
        prst.commit()

    def _mark_remove(self, patterns):
        prst = self.base._group_persistor
        q = CompsQuery(self.base.comps, prst,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.INSTALLED)
        solver = self.base._build_comps_solver()
        res = q.get(*patterns)
        for env_id in res.environments:
            solver.environment_remove(env_id)
        for grp_id in res.groups:
            solver.group_remove(grp_id)

        if res.environments:
            logger.info(_('Environments marked removed: %s'),
                        ','.join([prst.environment(e_id).ui_name
                                  for e_id in res.environments]))
        if res.groups:
            logger.info(_('Groups marked removed: %s'),
                        ','.join([prst.group(g_id).ui_name
                                  for g_id in res.groups]))
        prst.commit()

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
        parser.add_argument('subcmd', nargs='?', metavar='COMMAND')
        parser.add_argument('args', nargs='*')

    def configure(self):
        self._canonical()

        cmd = self.opts.subcmd
        args = self.opts.args

        cmds = ('list', 'info', 'remove', 'install', 'upgrade', 'summary', 'mark')
        if cmd not in cmds:
            logger.critical(_('Invalid groups sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise dnf.cli.CliError

        demands = self.cli.demands
        demands.sack_activation = True
        if cmd in ('install', 'mark', 'remove', 'upgrade'):
            demands.root_user = True
        if cmd == 'remove':
            demands.allow_erasing = True
            # temporary set to true because of migration
            # to new groups.json format
            # compat: set to False in 2.0.0
            demands.available_repos = True
        else:
            demands.available_repos = True

        commands.checkEnabledRepo(self.base)

        if cmd in ('install', 'remove', 'mark', 'info'):
            if not args:
                self.cli.optparser.print_help(self)
                raise dnf.cli.CliError

        if cmd in ('install', 'upgrade'):
            commands.checkGPGKey(self.base, self.cli)

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

        self.cli.demands.resolving = True
        if cmd == 'install':
            types, patterns = self._split_extcmds(extcmds)
            self._remark = True
            try:
                return self.base.env_group_install(patterns, types,
                                                   self.base.conf.strict)
            except dnf.exceptions.MarkingError as e:
                msg = _('No package %s%s%s available.')
                logger.info(msg, self.base.output.term.MODE['bold'], e,
                            self.base.output.term.MODE['normal'])
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Unable to find a mandatory group package."))
        if cmd == 'upgrade':
            return self.base.env_group_upgrade(extcmds)
        if cmd == 'remove':
            return self.base.env_group_remove(extcmds)

    def run_transaction(self):
        if not self._remark:
            return
        goal = self.base._goal
        pkgdb = self.base._yumdb
        names = goal.group_members
        for pkg in self.base.sack.query().installed().filter(name=names):
            db_pkg = pkgdb.get_package(pkg)
            reason = db_pkg.get('reason') or 'unknown'
            db_pkg.reason = goal.group_reason(pkg, reason)
