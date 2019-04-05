..
  Copyright (C) 2014-2018 Red Hat, Inc.

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


==============================
 Command Line Interface Hooks
==============================


.. module:: dnf.cli

:mod:`dnf.cli` is a part of DNF that contains code handling the command line tasks for DNF, like for instance ``dnf install emacs``, and outputs the results to the terminal. It is usually of no interest for DNF extension applications, but some parts of it described here can be used by the :doc:`api_plugins` to hook up custom commands.

When packaging your custom command, we recommend you to define a virtual provide in the form of ``Provides: dnf-command(<alias>)`` in the spec file. See :ref:`the virtual provides usage <command_provides-label>` for the details.

.. exception:: CliError

    Signals a CLI-specific problem (reading configuration, parsing user input, etc.). Derives from :exc:`dnf.exceptions.Error`.

.. class:: dnf.cli.demand.DemandSheet

  Instances are used to track requests of commands and plugins about how CLI should set up/handle other parts of CLI processing that are not under the command's/plugin's direct control. The boolean attributes of the sheet can not be reset once explicitly set, doing so raises an :exc:`AttributeError`.

    .. attribute:: allow_erasing

      If ``True``, the dependency solver is allowed to look for solutions that include removing other packages while looking to fulfill the current packaging requests. Defaults to ``False``. Also see :meth:`dnf.Base.resolve`.

    .. attribute:: available_repos

      If ``True`` during sack creation (:attr:`.sack_activation`), download and load into the sack the available repositories. Defaults to ``False``.

    .. attribute:: resolving

      If ``True`` at a place where the CLI would otherwise successfully exit, resolve the transaction for any outstanding packaging requests before exiting. Defaults to ``False``.

    .. attribute:: root_user

      ``True`` informs the CLI that the command can only succeed if the process's effective user id is ``0``, i.e. root. Defaults to ``False``.

    .. attribute:: sack_activation

      If ``True``, demand that the CLI sets up the :class:`~.Sack` before the command's :meth:`~.Command.run` method is executed. Defaults to ``False``.

      Depending on other demands and the user's configuration, this might or might not correctly trigger metadata download for the available repositories.

    .. attribute:: success_exit_status

      The return status of the DNF command on success. Defaults to ``0``.

    .. attribute:: transaction_display

      An additional instance of a subclass of :class:`dnf.callback.TransactionProgress` used to report information about an ongoing transaction.
.. class:: Command

  Base class of every DNF command.

  .. attribute:: aliases

    Sequence of strings naming the command from the command line. Must be a class variable. The list has to contain at least one string, the first string in the list is considered the canonical name. A command name can be contain only letters and dashes providing the name doesn't start with a dash.

  .. attribute:: base

    The :class:`dnf.Base` instance to use with this command.

  .. attribute:: cli

    The :class:`dnf.cli.Cli` instance to use with this command.

  .. attribute:: summary

    One line summary for the command as displayed by the CLI help.

  .. method:: __init__(cli)

    Command constructor which can be overridden. The constructor is called during
    CLI configure phase when one of the command's aliases is parsed from `dnf`
    commandline. `cli` is an instance of :class:`dnf.cli.Cli`.

  .. method:: pre_configure()

    Perform any pre-configuration on the command itself and on the CLI. Typically, the command
    implements this call to set up releasever or enable/disable repository. This method is called
    before configuration of repos.

  .. method:: configure()

    Perform any configuration on the command itself and on the CLI. Typically, the command implements this call to set up any :class:`demands <.DemandSheet>`, tweak the global configuration or the repository configuration. This method is called immediately after the CLI/extension is finished configuring DNF.

  .. method:: run()

    Run the command. This method is invoked by the CLI when this command is executed. Should raise :exc:`dnf.exceptions.Error` with a proper message if the command fails. Otherwise should return ``None``. Custom commands typically override this method and put their main work code here.

.. class:: Cli

  Manages the CLI, including reading configuration, parsing the command line and running commands.

  .. attribute:: demands

    An instance of :class:`~dnf.cli.demand.DemandSheet`, exposed to allow custom commands and plugins influence how the CLI will operate.

  .. method:: register_command(command_cls):

    Register new command. `command_cls` is a subclass of :class:`.Command`.

  .. method:: redirect_logger(self, stdout=None, stderr=None):

    Change minimal logger level for terminal output to stdout and stderr according to specific
    command requirements. For stdout and stderr use logging.INFO, logging.WARNING, etc.
