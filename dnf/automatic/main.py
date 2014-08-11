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
import dnf.const
import dnf.exceptions
import dnf.util
import dnf.yum.config
import dnf.yum.parser
import iniparse.compat
import logging
import socket

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
        else:
            assert False
    return emitters


def synopsis():
    print('usage: dnf-automatic <config-file>')
    return 1


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
        config_pp = dnf.yum.parser.ConfigPreProcessor(filename)
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
    base_config_file = dnf.yum.config.Option("/etc/dnf/dnf.conf")
    download_updates = dnf.yum.config.BoolOption(False)
    update_cmd = dnf.yum.config.Option("default")
    update_messages = dnf.yum.config.BoolOption(False)

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
    conf_fn = dnf.const.CONF_AUTOMATIC_FILENAME
    if len(args) == 1:
        conf_fn = args[0]
    elif len(args) > 1:
        return synopsis()

    try:
        conf = AutomaticConfig(conf_fn)
        with dnf.Base() as base:
            cli = dnf.cli.Cli(base)
            cli.read_conf_file(conf.commands.base_config_file,
                               overrides=conf.base_overrides)
            base_conf = base.conf
            base_conf.cachedir, _alt_dir = dnf.cli.cli.cachedir_fit(base_conf)
            logger.debug('Started dnf-automatic.')
            base.read_all_repos()
            base.fill_sack()
            base.upgrade_all()
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
