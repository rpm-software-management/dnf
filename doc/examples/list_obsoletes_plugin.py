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

"""A plugin that lists available packages filtered by their relation to the system."""

import dnf
import dnf.cli


# If you only plan to create a new dnf subcommand in a plugin
# you can use @dnf.plugin.register_command decorator instead of creating
# a Plugin class which only registers the command
# (for full-fledged Plugin class see examples/install_plugin.py)
@dnf.plugin.register_command
class Command(dnf.cli.Command):

    """A command that lists packages installed on the system that are
       obsoleted by packages in any known repository."""

    # An alias is needed to invoke the command from command line.
    aliases = ['foo']  # <-- SET YOUR ALIAS HERE.

    def configure(self, args):
        """Setup the demands."""
        # Repositories serve as sources of information about packages.
        self.cli.demands.available_repos = True
        # A sack is needed for querying.
        self.cli.demands.sack_activation = True

    def run(self, args):
        """Run the command."""

        obs_tuples = []
        # A query matches all available packages
        q = self.base.sack.query()

        if not args:
            # Narrow down query to match only installed packages
            inst = q.installed()
            # A dictionary containing list of obsoleted packages
            for new in q.filter(obsoletes=inst):
                obs_reldeps = new.obsoletes
                obsoleted = inst.filter(provides=obs_reldeps).run()
                obs_tuples.extend([(new, old) for old in obsoleted])
        else:
            for pkg_spec in args:
                # A subject serves for parsing package format from user input
                subj = dnf.subject.Subject(pkg_spec)
                # A query restricted to installed packages matching given subject
                inst = subj.get_best_query(self.base.sack).installed()
                for new in q.filter(obsoletes=inst):
                    obs_reldeps = new.obsoletes
                    obsoleted = inst.filter(provides=obs_reldeps).run()
                    obs_tuples.extend([(new, old) for old in obsoleted])

        if not obs_tuples:
            raise dnf.exceptions.Error('No matching Packages to list')

        for (new, old) in obs_tuples:
            print('%s.%s obsoletes %s.%s' %
                  (new.name, new.arch, old.name, old.arch))


