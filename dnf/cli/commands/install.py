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
    alternatives_provide = 'alternative-for({})'

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
        if not self.opts.filenames:
            commands._checkEnabledRepo(self.base)

    def run(self):
        err_pkgs = []
        errs = []
        error_module_specs = []

        nevra_forms = self._get_nevra_forms_from_command()

        self.cli._populate_update_security_filter(self.opts)
        if self.opts.command == 'localinstall' and (self.opts.grp_specs or self.opts.pkg_specs):
            self._log_not_valid_rpm_file_paths(self.opts.grp_specs)
            if self.base.conf.strict:
                raise dnf.exceptions.Error(_('Nothing to do.'))
        skipped_grp_specs = []
        if self.opts.grp_specs and self.opts.command != 'localinstall':
            if dnf.base.WITH_MODULES:
                try:
                    module_base = dnf.module.module_base.ModuleBase(self.base)
                    module_base.install(self.opts.grp_specs, strict=self.base.conf.strict)
                except dnf.exceptions.MarkingErrors as e:
                    if e.no_match_group_specs:
                        for e_spec in e.no_match_group_specs:
                            skipped_grp_specs.append(e_spec)
                    if e.error_group_specs:
                        for e_spec in e.error_group_specs:
                            error_module_specs.append("@" + e_spec)
                    module_depsolv_errors = e.module_depsolv_errors
                    if module_depsolv_errors:
                        logger.error(dnf.module.module_base.format_modular_solver_errors(
                            module_depsolv_errors[0]))
            else:
                skipped_grp_specs = self.opts.grp_specs
        if self.opts.filenames and nevra_forms:
            self._inform_not_a_valid_combination(self.opts.filenames)
            if self.base.conf.strict:
                raise dnf.exceptions.Error(_('Nothing to do.'))
        else:
            err_pkgs = self._install_files()

        if skipped_grp_specs and nevra_forms:
            self._inform_not_a_valid_combination(skipped_grp_specs)
            if self.base.conf.strict:
                raise dnf.exceptions.Error(_('Nothing to do.'))
        elif skipped_grp_specs and self.opts.command != 'localinstall':
            self._install_groups(skipped_grp_specs)

        if self.opts.command != 'localinstall':
            errs = self._install_packages(nevra_forms)

        if (len(errs) != 0 or len(err_pkgs) != 0 or error_module_specs) and self.base.conf.strict:
            raise dnf.exceptions.PackagesNotAvailableError(_("Unable to find a match"),
                                                           pkg_spec=' '.join(errs),
                                                           packages=err_pkgs)

    def _get_nevra_forms_from_command(self):
        if self.opts.command in self.nevra_forms:
            return [self.nevra_forms[self.opts.command]]
        else:
            return []

    def _log_not_valid_rpm_file_paths(self, grp_specs):
        group_names = map(lambda g: '@' + g, grp_specs)
        for pkg in chain(self.opts.pkg_specs, group_names):
            msg = _('Not a valid rpm file path: %s')
            logger.info(msg, self.base.output.term.bold(pkg))

    def _inform_not_a_valid_combination(self, forms):
        for form in forms:
            msg = _('Not a valid form: %s')
            logger.warning(msg, self.base.output.term.bold(form))

    def _install_files(self):
        err_pkgs = []
        strict = self.base.conf.strict
        for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=strict,
                                             progress=self.base.output.progress):
            try:
                self.base.package_install(pkg, strict=strict)
            except dnf.exceptions.MarkingError:
                msg = _('No match for argument: %s')
                logger.info(msg, self.base.output.term.bold(pkg.location))
                err_pkgs.append(pkg)

        return err_pkgs

    def _install_groups(self, grp_specs):
        try:
            self.base.env_group_install(grp_specs,
                                        tuple(self.base.conf.group_package_types),
                                        strict=self.base.conf.strict)
        except dnf.exceptions.Error:
            if self.base.conf.strict:
                raise

    def _report_alternatives(self, pkg_spec):
        query = self.base.sack.query().filterm(
            provides=self.alternatives_provide.format(pkg_spec))
        if query:
            msg = _('There are following alternatives for "{0}": {1}')
            logger.info(msg.format(
                pkg_spec,
                ', '.join(sorted(set([alt.name for alt in query])))))

    def _install_packages(self, nevra_forms):
        errs = []
        strict = self.base.conf.strict
        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.install(pkg_spec, strict=strict, forms=nevra_forms)
            except dnf.exceptions.MarkingError as e:
                msg = '{}: {}'.format(e.value, self.base.output.term.bold(pkg_spec))
                logger.info(msg)
                self.base._report_icase_hint(pkg_spec)
                self._report_alternatives(pkg_spec)
                errs.append(pkg_spec)

        return errs
