# Copyright 2005 Duke University
# Copyright (C) 2012-2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Entrance point for the yum command line interface.
"""

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import ucd
from dnf.cli.utils import show_lock_owner
from dnf.i18n import _

import dnf.cli
import dnf.cli.cli
import dnf.cli.option_parser
import dnf.exceptions
import dnf.i18n
import dnf.logging
import dnf.util
import errno
import logging
import os
import os.path
import sys

logger = logging.getLogger("dnf")


def ex_IOError(e):
    logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)
    logger.critical(ucd(e))
    return 1


def ex_Error(e):
    logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)
    if e.value is not None:
        logger.critical(_('Error: %s'), ucd(e))
    return 1


def main(args):
    try:
        with dnf.cli.cli.BaseCli() as base:
            return _main(base, args)
    except dnf.exceptions.ProcessLockError as e:
        logger.critical(e.value)
        show_lock_owner(e.pid)
        return 1
    except dnf.exceptions.LockError as e:
        logger.critical(e.value)
        return 1
    except dnf.exceptions.DepsolveError as e:
        return 1
    except dnf.exceptions.Error as e:
        return ex_Error(e)
    except IOError as e:
        return ex_IOError(e)
    except KeyboardInterrupt as e:
        logger.critical('{}: {}'.format(type(e).__name__, "Terminated."))
        return 1


def _main(base, args):
    """Run the dnf program from a command line interface."""

    dnf.i18n.setup_locale()
    dnf.i18n.setup_stdout()

    # our core object for the cli
    base._logging._presetup()
    cli = dnf.cli.cli.Cli(base)

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        cli.configure(list(map(ucd, args)))
    except dnf.exceptions.LockError:
        raise
    except (IOError, OSError) as e:
        return ex_IOError(e)

    return cli_run(cli, base)


def cli_run(cli, base):
    # Try to open the current directory to see if we have
    # read and execute access. If not, chdir to /
    try:
        f = open(".")
    except IOError as e:
        if e.errno == errno.EACCES:
            logger.critical(_('No read/execute access in current directory, moving to /'))
            os.chdir("/")
    else:
        f.close()

    try:
        cli.run()
    except dnf.exceptions.LockError:
        raise
    except (IOError, OSError) as e:
        return ex_IOError(e)

    if cli.demands.resolving:
        try:
            ret = resolving(cli, base)
        except dnf.exceptions.DepsolveError as e:
            ex_Error(e)
            if not cli.demands.allow_erasing:
                logger.info(_("(try to add '%s' to command line to"
                              " replace conflicting packages)"),
                            "--allowerasing")
            raise
        if ret:
            return ret

    cli.command.run_transaction()
    return cli.demands.success_exit_status


def resolving(cli, base):
    """Perform the depsolve, download and RPM transaction stage."""

    if base.transaction is None:
        base.resolve(cli.demands.allow_erasing)
        logger.info(_('Dependencies resolved.'))

    # Run the transaction
    displays = []
    if cli.demands.transaction_display is not None:
        displays.append(cli.demands.transaction_display)
    try:
        base.do_transaction(display=displays)
    except dnf.cli.CliError as exc:
        logger.error(ucd(exc))
        return 1
    except dnf.exceptions.TransactionCheckError as err:
        for msg in cli.command.get_error_output(err):
            logger.critical(msg)
        return 1
    except IOError as e:
        return ex_IOError(e)
    else:
        logger.info(_('Complete!'))
    return 0


def user_main(args, exit_code=False):
    """Call one of the multiple main() functions based on environment variables.

    :param args: command line arguments passed into yum
    :param exit_code: if *exit_code* is True, this function will exit
       python with its exit code when it has finished executing.
       Otherwise, it will return its exit code.
    :return: the exit code from dnf.yum execution
    """

    errcode = main(args)
    if exit_code:
        sys.exit(errcode)
    return errcode


if __name__ == "__main__":
    user_main(sys.argv[1:], exit_code=True)
