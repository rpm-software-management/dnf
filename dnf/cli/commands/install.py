# install.py
# Install CLI command.
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
from __future__ import unicode_literals
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _
from itertools import chain

import dnf.exceptions
import hawkey
import logging

logger = logging.getLogger('dnf')


class InstallCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    install command.
    """
    nevra_forms = {'install-n': hawkey.FORM_NAME,
                   'install-na': hawkey.FORM_NA,
                   'install-nevra': hawkey.FORM_NEVRA}

    aliases = ('install', 'localinstall') + tuple(nevra_forms.keys())
    summary = _('install a package or packages on your system')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('package', nargs='+', metavar=_('PACKAGE'),
                          action=OptionParser.ParseSpecGroupFileCallback,
                          help=_('Package to install'))

    def configure(self):
        """Verify that conditions are met so that this command can run.
        That there are enabled repositories with gpg keys, and that
        this command is called with appropriate arguments.
        """
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        if not self.opts.filenames:
            commands._checkEnabledRepo(self.base)

    def run(self):
        strict = self.base.conf.strict
        forms = [self.nevra_forms[command] for command in self.opts.command
                 if command in list(self.nevra_forms.keys())]

        self.cli._populate_update_security_filter(self.opts, self.base.sack.query())

        # localinstall valid arguments check
        nonfilenames = self.opts.grp_specs or self.opts.pkg_specs
        if self.opts.command == ['localinstall'] and nonfilenames:
            group_names = map(lambda g: '@' + g, self.opts.grp_specs)
            for pkg in chain(self.opts.pkg_specs, group_names):
                msg = _('Not a valid rpm file path: %s')
                logger.info(msg, self.base.output.term.bold(pkg))
            if strict:
                raise dnf.exceptions.Error(_('No packages marked for install.'))

        # Install files.
        err_pkgs = []
        if self.opts.filenames and forms:
            for filename in self.opts.filenames:
                msg = _('Not a valid form: %s')
                logger.warning(msg, self.base.output.term.bold(filename))
            if strict:
                raise dnf.exceptions.Error(_('No packages marked for install.'))
        else:
            for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=strict):
                try:
                    self.base.package_install(pkg, strict=strict)
                except dnf.exceptions.MarkingError:
                    msg = _('No match for argument: %s')
                    logger.info(msg, self.base.output.term.bold(pkg.location))
                    err_pkgs.append(pkg)

        # Install groups.
        if self.opts.grp_specs and forms:
            for grp_spec in self.opts.grp_specs:
                msg = _('Not a valid form: %s')
                logger.warning(msg, self.base.output.term.bold(grp_spec))
            if strict:
                raise dnf.exceptions.Error(_('No packages marked for install.'))
        elif self.opts.grp_specs and self.opts.command != ['localinstall']:
            self.base.read_comps(arch_filter=True)
            try:
                self.base.env_group_install(self.opts.grp_specs,
                                            tuple(self.base.conf.group_package_types),
                                            strict=strict)
            except dnf.exceptions.Error:
                if self.base.conf.strict:
                    raise

        # Install packages.
        errs = []
        if self.opts.command != ['localinstall']:
            for pkg_spec in self.opts.pkg_specs:
                try:
                    self.base.install(pkg_spec, strict=strict, forms=forms)
                except dnf.exceptions.MarkingError:
                    msg = _('No match for argument: %s')
                    logger.info(msg, self.base.output.term.bold(pkg_spec))
                    errs.append(pkg_spec)

        if (len(errs) != 0 or len(err_pkgs) != 0) and self.base.conf.strict:
            raise dnf.exceptions.PackagesNotAvailableError(
                _("Unable to find a match"), pkg_spec=' '.join(errs),
                packages=err_pkgs)
