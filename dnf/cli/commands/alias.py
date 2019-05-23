# alias.py
# Alias CLI command.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os.path

import dnf.cli
import dnf.cli.aliases
from dnf.cli import commands
import dnf.conf
import dnf.exceptions
from dnf.i18n import _

logger = logging.getLogger('dnf')


class AliasCommand(commands.Command):
    aliases = ('alias',)
    summary = _('List or create command aliases')

    @staticmethod
    def set_argparser(parser):
        enable_group = parser.add_mutually_exclusive_group()
        enable_group.add_argument(
            '--enable-resolving', default=False, action='store_true',
            help=_('enable aliases resolving'))
        enable_group.add_argument(
            '--disable-resolving', default=False, action='store_true',
            help=_('disable aliases resolving'))
        parser.add_argument("subcommand", nargs='?', default='list',
                            choices=['add', 'list', 'delete'],
                            help=_("action to do with aliases"))
        parser.add_argument("alias", nargs="*", metavar="command[=result]",
                            help=_("alias definition"))

    def configure(self):
        demands = self.cli.demands
        if self.opts.subcommand in ('add', 'delete'):
            demands.root_user = True
        self.aliases_base = dnf.cli.aliases.Aliases()
        self.aliases_base._load_aliases()
        self.resolving_enabled = self.aliases_base.enabled
        self._update_config_from_options()

    def _update_config_from_options(self):
        enabled = None
        if self.opts.enable_resolving:
            enabled = True
            logger.info(_("Aliases are now enabled"))
        if self.opts.disable_resolving:
            enabled = False
            logger.info(_("Aliases are now disabled"))

        if enabled is not None:
            if not os.path.exists(dnf.cli.aliases.ALIASES_CONF_PATH):
                open(dnf.cli.aliases.ALIASES_CONF_PATH, 'w').close()
            dnf.conf.BaseConfig.write_raw_configfile(
                dnf.cli.aliases.ALIASES_CONF_PATH,
                'main', None, {'enabled': enabled})
            if not self.aliases_base._disabled_by_environ():
                self.aliases_base.enabled = enabled

    def _parse_option_alias(self):
        new_aliases = {}
        for alias in self.opts.alias:
            alias = alias.split('=', 1)
            cmd = alias[0].strip()
            if len(cmd.split()) != 1:
                logger.warning(_("Invalid alias key: %s"), cmd)
                continue
            if cmd.startswith('-'):
                logger.warning(_("Invalid alias key: %s"), cmd)
                continue
            if len(alias) == 1:
                logger.warning(_("Alias argument has no value: %s"), cmd)
                continue
            new_aliases[cmd] = alias[1].split()
        return new_aliases

    def _load_user_aliases(self):
        if not os.path.exists(dnf.cli.aliases.ALIASES_USER_PATH):
            open(dnf.cli.aliases.ALIASES_USER_PATH, 'w').close()
        try:
            conf = dnf.cli.aliases.AliasesConfig(
                dnf.cli.aliases.ALIASES_USER_PATH)
        except dnf.exceptions.ConfigError as e:
            logger.warning(_('Config error: %s'), e)
            return None
        return conf

    def _store_user_aliases(self, user_aliases, enabled):
        fileobj = open(dnf.cli.aliases.ALIASES_USER_PATH, 'w')
        output = "[main]\n"
        output += "enabled = {}\n\n".format(enabled)
        output += "[aliases]\n"
        for key, value in user_aliases.items():
            output += "{} = {}\n".format(key, ' '.join(value))
        fileobj.write(output)

    def add_aliases(self, aliases):
        conf = self._load_user_aliases()
        user_aliases = conf.aliases
        if user_aliases is None:
            return

        user_aliases.update(aliases)

        self._store_user_aliases(user_aliases, conf.enabled)
        logger.info(_("Aliases added: %s"), ', '.join(aliases.keys()))

    def remove_aliases(self, cmds):
        conf = self._load_user_aliases()
        user_aliases = conf.aliases
        if user_aliases is None:
            return

        valid_cmds = []
        for cmd in cmds:
            try:
                del user_aliases[cmd]
                valid_cmds.append(cmd)
            except KeyError:
                logger.info(_("Alias not found: %s"), cmd)

        self._store_user_aliases(user_aliases, conf.enabled)
        logger.info(_("Aliases deleted: %s"), ', '.join(valid_cmds))

    def list_alias(self, cmd):
        args = [cmd]
        try:
            args = self.aliases_base._resolve(args)
        except dnf.exceptions.Error as e:
            logger.error(
                _('%s, alias %s="%s"'), e, cmd, (' ').join(self.aliases_base.aliases[cmd]))
        else:
            print(_("Alias %s='%s'") % (cmd, " ".join(args)))

    def run(self):
        if not self.aliases_base.enabled:
            logger.warning(_("Aliases resolving is disabled."))

        if self.opts.subcommand == 'add':  # Add new alias
            aliases = self._parse_option_alias()
            if not aliases:
                raise dnf.exceptions.Error(_("No aliases specified."))
            self.add_aliases(aliases)
            return

        if self.opts.subcommand == 'delete':  # Remove alias
            cmds = self.opts.alias
            if cmds == []:
                raise dnf.exceptions.Error(_("No alias specified."))
            self.remove_aliases(cmds)
            return

        if not self.opts.alias:  # List all aliases
            if not self.aliases_base.aliases:
                logger.info(_("No aliases defined."))
                return
            for cmd in self.aliases_base.aliases:
                self.list_alias(cmd)
        else:  # List alias by key
            for cmd in self.opts.alias:
                if cmd not in self.aliases_base.aliases:
                    logger.info(_("No match for alias: %s") % cmd)
                    continue
                self.list_alias(cmd)
