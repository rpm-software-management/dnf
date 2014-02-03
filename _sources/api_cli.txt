==============================
 Command Line Interface Hooks
==============================

.. module:: dnf.cli

:mod:`dnf.cli` is a part of DNF that contains code handling the command line tasks for DNF, like for instance ``dnf install emacs``, and outputs the results to the terminal. It is usually of no interest for DNF extension applications, but some parts of it described here can be used by the :doc:`api_plugins` to hook up custom commands.

.. class:: Command

  Base class of every DNF command.

  .. attribute:: aliases

    Sequence of strings naming the command from the command line. Must be a class variable. The list has to contain at least one string, the first string in the list is considered the canonical name. A command name can be contain only letters and dashes providing the name doesn't start with a dash.

  .. method:: run(args)

    Run the command. This method is invoked by the CLI when this command is executed. `args` is a list of additional arguments to the command, entered after the command's name on the command line. Should raise :exc:`dnf.exceptions.Error` with a proper message if the command fails. Otherwise should return ``None``. Custom commands typically override this method.

.. class:: Cli

  Manages the CLI, including reading configuration, parsing the command line and running commands.

  .. method:: register_command(command_cls):

    Register new command. `command_cls` is a subclass of :class:`.Command`.
