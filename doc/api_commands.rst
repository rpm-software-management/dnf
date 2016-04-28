..
  Copyright (C) 2016  Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, write to the
  Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
  02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
  source code or documentation are not subject to the GNU General Public
  License and may only be used or replicated with the express permission of
  Red Hat, Inc.

===================
 Command Interface
===================

DNF command is a Python class fullfilling the following criteria:

1. it derives from :class:`dnf.cli.Command`,
2. it is made available in a Python module stored in one of the :attr:`.Conf.pluginpath`,
3. provides its own :attr:`~.Command.aliases` and :meth:`~.Command.run`.

DNF command needs to be registered either from a DNF plugin calling
`cli.register_command(CommandClass)` or decorating command class with
`@dnf.plugin.register_command` decorator.

When DNF CLI runs it loads the plugins and commands found in the paths during the
CLI's initialization.

.. class:: dnf.cli.Command

  The base class all DNF commands derive from.

  .. attribute:: aliases

    List of names this command is associated with. E.g. ('upgrade', 'update').
    The string can only contain alphanumeric characters and underscores.

  .. attribute:: summary

    A short description of command used for `--help`.

  .. attribute:: base

    Reference to global `cli.base` to be used whenever you need to work with
    base attributes inside the command.

  .. method:: __init__(cli)

    Command constructor which can be overriden. The constructor is called during
    CLI configure phase when one of the command's aliases is parsed from `dnf`
    commandline.
    `cli` is an instance of :class:`dnf.cli.Cli.

  .. method:: configure(args)

    Command can override this. This hook is called immediately after the CLI/extension
    is finished configuring DNF. The command can use this to tweak the global
    configuration or the repository configuration.

  .. method:: run(args)

    Command should override this. This hook is called in the CLI run phase.
    This is the method which does the command's main job.

