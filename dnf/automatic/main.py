# __init__.py
# dnf.automatic CLI
#
# Copyright (C) 2014  Red Hat, Inc.
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
import dnf.conf.parser
import dnf.const
import dnf.exceptions
import dnf.util
import dnf.logging
import dnf.yum.config
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
    for name in conf.emitters.emit_via:
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
            assert False
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

    def _load(self, filename):
        parser = iniparse.compat.ConfigParser()
        config_pp = dnf.conf.parser.ConfigPreProcessor(filename)
        try:
            parser.readfp(config_pp)
        except iniparse.compat.ParsingError as e:
            raise dnf.exceptions.ConfigError("Parsing file failed: %s" % e)

        self.commands.populate(parser, 'commands')
        self.email.populate(parser, 'email')
        self.emitters.populate(parser, 'emitters')
        self._parser = parser

    @property
    def base_overrides(self):
        return {k: v for (k, v) in self._parser.items('base')}


class CommandsConfig(dnf.yum.config.BaseConfig):
    apply_updates = dnf.yum.config.BoolOption(False)
    base_config_file = dnf.yum.config.Option('/etc/dnf/dnf.conf')
    download_updates = dnf.yum.config.BoolOption(False)
    upgrade_type = dnf.yum.config.SelectionOption(
        'default', ('default', 'security'))
    random_sleep = dnf.yum.config.SecondsOption(300)

    def imply(self):
        if self.apply_updates:
            self.download_updates = True


class EmailConfig(dnf.yum.config.BaseConfig):
    email_to = dnf.yum.config.ListOption(["root"])
    email_from = dnf.yum.config.Option("root")
    email_host = dnf.yum.config.Option("localhost")
    email_port = dnf.yum.config.IntOption(25)


class EmittersConfig(dnf.yum.config.BaseConfig):
    emit_via = dnf.yum.config.ListOption(['email', 'stdio'])
    output_width = dnf.yum.config.IntOption(80)
    system_name = dnf.yum.config.Option(socket.gethostname())


def main(args):
    (opts, parser) = parse_arguments(args)

    try:
        conf = AutomaticConfig(opts.conf_path)
        with dnf.Base() as base:
            cli = dnf.cli.Cli(base)
            cli.read_conf_file(conf.commands.base_config_file,
                               overrides=conf.base_overrides)
            base_conf = base.conf
            base_conf.cachedir, _alt_dir = dnf.cli.cli.cachedir_fit(base_conf)
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

