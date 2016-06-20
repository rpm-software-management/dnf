# Copyright (C) 2015  Red Hat, Inc.
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

"""A plugin that ensures that given features are present."""


import dnf.cli


# The parent class allows registration to the CLI manager.
class Command(dnf.cli.Command):

    """A command that ensures that given features are present."""

    # An alias is needed to invoke the command from command line.
    aliases = ['foo']  # <-- SET YOUR ALIAS HERE.

    def configure(self, args):
        """Setup the demands."""
        # Repositories are needed if we want to install anything.
        self.cli.demands.available_repos = True
        # A sack is required by marking methods and dependency resolving.
        self.cli.demands.sack_activation = True
        # Resolving performs a transaction that installs the packages.
        self.cli.demands.resolving = True
        # Based on the system, privileges are required to do an installation.
        self.cli.demands.root_user = True  # <-- SET YOUR FLAG HERE.

    @staticmethod
    def parse_args(args):
        """Parse command line arguments."""
        # -- IMPLEMENT YOUR PARSER HERE. --
        if not args:
            raise dnf.cli.CliError('invalid command line arguments')
        ftr_specs, rpm_specs, grp_specs = set(), set(), set()
        for arg in args:
            if arg.startswith('@'):
                grp_specs.add(arg[1:])
            elif arg.endswith('.rpm'):
                rpm_specs.add(arg)
            else:
                ftr_specs.add(arg)
        return ftr_specs, rpm_specs, grp_specs

    def run(self, args):
        """Run the command."""
        ftr_specs, rpm_specs, grp_specs = self.parse_args(args)
        # Feature marking methods set the user request.
        for ftr_spec in ftr_specs:
            try:
                self.base.install(ftr_spec)
            except dnf.exceptions.MarkingError:
                raise dnf.exceptions.Error('feature(s) not found: ' + ftr_spec)
        # Package marking methods set the user request.
        try:
            self.base.package_install(self.base.add_remote_rpm(rpm_specs))
        except EnvironmentError as e:
            raise dnf.exceptions.Error(e)
        # Comps data reading initializes the base.comps attribute.
        if grp_specs:
            self.base.read_comps()
        # Group marking methods set the user request.
        for grp_spec in grp_specs:
            group = self.base.comps.group_by_pattern(grp_spec)
            if not group:
                raise dnf.exceptions.Error('group not found: ' + grp_spec)
            self.base.group_install(group, ['mandatory', 'default'])


# Every plugin must be a subclass of dnf.Plugin.
class Plugin(dnf.Plugin):

    """A plugin that registers our custom command."""

    # Every plugin must provide its name.
    name = 'foo'  # <-- SET YOUR NAME HERE.

    # Every plugin must provide its own initialization function.
    def __init__(self, base, cli):
        """Initialize the plugin."""
        super(Plugin, self).__init__(base, cli)
        if cli:
            cli.register_command(Command)
