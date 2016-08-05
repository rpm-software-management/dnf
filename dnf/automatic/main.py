# __init__.py
# dnf.automatic CLI
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
from dnf.i18n import _, ucd
import dnf
import dnf.automatic.emitter
import dnf.cli
import dnf.cli.cli
import dnf.cli.output
import dnf.conf
import dnf.conf.parser
import dnf.const
import dnf.exceptions
import dnf.util
import dnf.logging
import hawkey
import iniparse.compat
import logging
import socket
import argparse
import random
import time

logger = logging.getLogger('dnf')


def build_emitters(conf):
    emitters = dnf.util.MultiCallList([])
    system_name = conf.emitters.system_name
    emit_via = conf.emitters.emit_via
    if emit_via:
        for name in emit_via:
            if name == 'email':
                emitter = dnf.automatic.emitter.EmailEmitter(system_name, conf.email)
                emitters.append(emitter)
            elif name == 'stdio':
                emitter = dnf.automatic.emitter.StdIoEmitter(system_name)
                emitters.append(emitter)
            elif name == 'motd':
                emitter = dnf.automatic.emitter.MotdEmitter(system_name)
                emitters.append(emitter)
            else:
                raise dnf.exceptions.ConfigError("Unknowr emitter option: %s" % name)
    return emitters


def parse_arguments(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('conf_path', nargs='?', default=dnf.const.CONF_AUTOMATIC_FILENAME)
    parser.add_argument('--timer', action='store_true')

    return parser.parse_args(args), parser


class AutomaticConfig(object):
    def __init__(self, filename):
        self.commands = CommandsConfig()
        self.email = EmailConfig()
        self.emitters = EmittersConfig()
        self._parser = None
        self._load(filename)
        self.commands.imply()
        self.filename = filename

    def _load(self, filename):
        parser = iniparse.compat.ConfigParser()
        config_pp = dnf.conf.parser.ConfigPreProcessor(filename)
        try:
            parser.readfp(config_pp)
        except iniparse.compat.ParsingError as e:
            raise dnf.exceptions.ConfigError("Parsing file failed: %s" % e)

        self.commands._populate(parser, 'commands', filename, dnf.conf.PRIO_AUTOMATICCONFIG)
        self.email._populate(parser, 'email', filename, dnf.conf.PRIO_AUTOMATICCONFIG)
        self.emitters._populate(parser, 'emitters', filename, dnf.conf.PRIO_AUTOMATICCONFIG)
        self._parser = parser

    def update_baseconf(self, baseconf):
        baseconf._populate(self._parser, 'base', self.filename, dnf.conf.PRIO_AUTOMATICCONFIG)


class CommandsConfig(dnf.conf.BaseConfig):
    def __init__(self, section='commands', parser=None):
        super(CommandsConfig, self).__init__(section, parser)
        self._add_option('apply_updates',  dnf.conf.BoolOption(False))
        self._add_option('base_config_file',  dnf.conf.Option('/etc/dnf/dnf.conf'))
        self._add_option('download_updates',  dnf.conf.BoolOption(False))
        self._add_option('upgrade_type',  dnf.conf.SelectionOption('default',
                                        choices=('default', 'security')))
        self._add_option('random_sleep',  dnf.conf.SecondsOption(300))

    def imply(self):
        if self.apply_updates:
            self._set_value('download_updates', True, dnf.conf.PRIO_RUNTIME)


class EmailConfig(dnf.conf.BaseConfig):
    def __init__(self, section='email', parser=None):
        super(EmailConfig, self).__init__(section, parser)
        self._add_option('email_to',  dnf.conf.ListOption(["root"]))
        self._add_option('email_from',  dnf.conf.Option("root"))
        self._add_option('email_host',  dnf.conf.Option("localhost"))
        self._add_option('email_port',  dnf.conf.IntOption(25))

class EmittersConfig(dnf.conf.BaseConfig):
    def __init__(self, section='emiter', parser=None):
        super(EmittersConfig, self).__init__(section, parser)
        self._add_option('emit_via',  dnf.conf.ListOption(['email', 'stdio']))
        self._add_option('output_width',  dnf.conf.IntOption(80))
        self._add_option('system_name',  dnf.conf.Option(socket.gethostname()))


def main(args):
    (opts, parser) = parse_arguments(args)

    try:
        conf = AutomaticConfig(opts.conf_path)
        with dnf.Base() as base:
            cli = dnf.cli.Cli(base)
            cli._read_conf_file()
            conf.update_baseconf(base.conf)
            base.init_plugins(cli=cli)
            logger.debug('Started dnf-automatic.')

            if opts.timer:
                sleeper = random.randint(0, conf.commands.random_sleep)
                logger.debug('Sleep for %s seconds', sleeper)
                time.sleep(sleeper)

            base.read_all_repos()
            base.fill_sack()
            upgrade(base, conf.commands.upgrade_type)
            base.resolve()
            output = dnf.cli.output.Output(base, base.conf)
            trans = base.transaction
            if not trans:
                return 0

            lst = output.list_transaction(trans)
            emitters = build_emitters(conf)
            emitters.notify_available(lst)
            if not conf.commands.download_updates:
                emitters.commit()
                return 0

            base.download_packages(trans.install_set)
            emitters.notify_downloaded()
            if not conf.commands.apply_updates:
                emitters.commit()
                return 0

            base.do_transaction()
            emitters.notify_applied()
            emitters.commit()
    except dnf.exceptions.Error as exc:
        logger.error(_('Error: %s'), ucd(exc))
        return 1
    return 0


def upgrade(base, upgrade_type):
    if upgrade_type == 'default':
        base.upgrade_all()
    elif upgrade_type == 'security':
        for pkg in base.sack.query().installed():
            for advisory in pkg.get_advisories(hawkey.GT):
                if advisory.type != hawkey.ADVISORY_SECURITY:
                    continue
                base.upgrade(pkg.name)
    else:
        assert False
