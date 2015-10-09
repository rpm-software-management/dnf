# install.py
# Install CLI command.
#
# Copyright (C) 2014-2015 Red Hat, Inc.
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
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

import dnf.exceptions
import functools
import logging
import operator

logger = logging.getLogger('dnf')


class InstallCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    install command.
    """

    aliases = ('install',)
    summary = _("Install a package or packages on your system")
    usage = "%s..." % _('PACKAGE')

    @staticmethod
    def set_argparse_subparser(parser):
        parser.add_argument('package', nargs='+',
                            action=OptionParser.ParseSpecGroupFileCallback)

    def configure(self, args):
        """Verify that conditions are met so that this command can run.
        That there are enabled repositories with gpg keys, and that
        this command is called with appropriate arguments.
        """
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands.checkGPGKey(self.base, self.cli)
        commands.checkEnabledRepo(self.base, self.opts.filenames)

    def run(self, extcmds):
        strict = self.base.conf.strict
        package_install_fnc = functools.partial(self.base.package_install,
                                                strict=strict)

        # Install files.
        local_pkgs = map(self.base.add_remote_rpm, self.opts.filenames)
        # try to install packages with higher version first
        local_pkgs = sorted(local_pkgs, reverse=True)
        results = map(package_install_fnc, local_pkgs)
        done = functools.reduce(operator.or_, results, False)

        # Install groups.
        if self.opts.grp_specs:
            self.base.read_comps()
            try:
                self.base.env_group_install(self.opts.grp_specs,
                                            dnf.const.GROUP_PACKAGE_TYPES,
                                            strict=strict)
            except dnf.exceptions.Error:
                if self.base.conf.strict:
                    raise
            done = True

        # Install packages.
        errs = []
        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.install(pkg_spec, strict=strict)
            except dnf.exceptions.MarkingError:
                msg = _('No package %s%s%s available.')
                logger.info(msg, self.base.output.term.MODE['bold'], pkg_spec,
                            self.base.output.term.MODE['normal'])
                errs.append(pkg_spec)
            done = True
        if len(errs) != 0 and self.base.conf.strict:
            raise dnf.exceptions.PackagesNotAvailableError(_("Unable to find a match."), packages=errs)

        if not done:
            raise dnf.exceptions.Error(_('Nothing to do.'))
