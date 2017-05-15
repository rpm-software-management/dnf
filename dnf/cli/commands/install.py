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

import logging
from itertools import chain

import hawkey

import dnf.exceptions
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

logger = logging.getLogger('dnf')


class InstallCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    install command.
    """
    nevra_forms = {'install-n': hawkey.FORM_NAME,
                   'install-na': hawkey.FORM_NA,
                   'install-nevra': hawkey.FORM_NEVRA}

    aliases = ('install', 'localinstall', 'in') + tuple(nevra_forms.keys())
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
        commands._checkEnabledRepo(self.base, self.opts.filenames)

    def run(self):
        if not self.opts.legacy:
            self.install_module_profiles()
            return

        nevra_forms = self._get_nevra_forms_from_command()

        self.cli._populate_update_security_filter(self.opts, minimal=True)
        self._check_arguments_validity_for_localinstall()
        err_pkgs = self._decide_to_install_files(nevra_forms)
        self._decide_to_install_groups(nevra_forms)
        errs = self._install_packages_if_not_locallinstall(nevra_forms)
        self._raise_no_match_if_any_error_and_strict(err_pkgs, errs)

    def install_module_profiles(self):
        self.cli.demands.transaction_display = self.base.repo_module_dict.transaction_callback

        self.base.repo_module_dict.install(self.opts.pkg_specs, True)
        self.base.repo_module_dict.install(self.opts.grp_specs, True)

    def _get_nevra_forms_from_command(self):
        return [self.nevra_forms[command]
                for command in self.opts.command
                if command in list(self.nevra_forms.keys())
                ]

    def _check_arguments_validity_for_localinstall(self):
        nonfilenames = self.opts.grp_specs or self.opts.pkg_specs

        if self._is_localinstall_command() and nonfilenames:
            self._log_not_valid_rpm_file_paths()
            if self.base.conf.strict:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    def _is_localinstall_command(self):
        return self.opts.command == ['localinstall']

    def _log_not_valid_rpm_file_paths(self):
        group_names = map(lambda g: '@' + g, self.opts.grp_specs)
        for pkg in chain(self.opts.pkg_specs, group_names):
            msg = _('Not a valid rpm file path: %s')
            logger.info(msg, self.base.output.term.bold(pkg))

    def _decide_to_install_files(self, nevra_forms):
        if self.opts.filenames and nevra_forms:
            self._inform_not_a_valid_form(self.opts.filenames)
        else:
            return self._install_files()

        return []

    def _inform_not_a_valid_form(self, forms):
        for form in forms:
            msg = _('Not a valid form: %s')
            logger.warning(msg, self.base.output.term.bold(form))
        self._raise_nothing_to_do_if_strict()

    def _raise_nothing_to_do_if_strict(self):
        if self.base.conf.strict:
            raise dnf.exceptions.Error(_('Nothing to do.'))

    def _install_files(self):
        err_pkgs = []
        strict = self.base.conf.strict
        for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=strict):
            try:
                self.base.package_install(pkg, strict=strict)
            except dnf.exceptions.MarkingError:
                msg = _('No match for argument: %s')
                logger.info(msg, self.base.output.term.bold(pkg.location))
                err_pkgs.append(pkg)

        return err_pkgs

    def _decide_to_install_groups(self, nevra_forms):
        if self.opts.grp_specs and nevra_forms:
            self._inform_not_a_valid_form(self.opts.grp_specs)
        elif self.opts.grp_specs and self.opts.command != ['localinstall']:
            self._install_groups()

    def _install_groups(self):
        self.base.read_comps(arch_filter=True)
        try:
            self.base.env_group_install(self.opts.grp_specs,
                                        self.base.conf.group_package_types,
                                        strict=self.base.conf.strict)
        except dnf.exceptions.Error:
            if self.base.conf.strict:
                raise

    def _install_packages_if_not_locallinstall(self, nevra_forms):
        if self.opts.command != ['localinstall']:
            return self._install_packages(nevra_forms)

    def _install_packages(self, nevra_forms):
        errs = []
        strict = self.base.conf.strict
        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.install(pkg_spec, strict=strict, forms=nevra_forms)
            except dnf.exceptions.MarkingError:
                msg = _('No package %s available.')
                logger.info(msg, self.base.output.term.bold(pkg_spec))
                self.base._report_icase_hint(pkg_spec)
                errs.append(pkg_spec)

        return errs

    def _raise_no_match_if_any_error_and_strict(self, err_pkgs, errs):
        if (len(errs) != 0 or len(err_pkgs) != 0) and self.base.conf.strict:
            raise dnf.exceptions.PackagesNotAvailableError(
                _("Unable to find a match"), pkg_spec=' '.join(errs),
                packages=err_pkgs)
