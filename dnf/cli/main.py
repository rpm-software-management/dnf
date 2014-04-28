# Copyright 2005 Duke University
# Copyright (C) 2012-2013  Red Hat, Inc.
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
from dnf.pycomp import unicode

import sys


def suppress_keyboard_interrupt_message():
    """Prevent unsightly KeyboardInterrupt tracebacks.

    Nothing will be printed to the terminal after an uncaught
    :class:`exceptions.KeyboardInterrupt`.

    """
    old_excepthook = sys.excepthook

    def new_hook(type, value, traceback):
        if type != KeyboardInterrupt:
            old_excepthook(type, value, traceback)
        else:
            pass

    sys.excepthook = new_hook


# do this ASAP to prevent tracebacks after ^C during imports
suppress_keyboard_interrupt_message()

from dnf.cli.utils import show_lock_owner
from dnf.i18n import _

import dnf.cli.cli
import dnf.exceptions
import dnf.i18n
import dnf.logging
import dnf.util
import errno
import logging
import os
import os.path

logger = logging.getLogger("dnf")


def ex_IOError(e):
    logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)
    logger.critical(unicode(e))
    return 1


def ex_Error(e):
    if e.value is not None:
        logger.critical(_('Error: %s'), unicode(e))
    return 1


def main(args):
    try:
        with dnf.cli.cli.BaseCli() as base:
            return _main(base, args)
    except dnf.exceptions.ProcessLockError as e:
        logger.critical(e.value)
        show_lock_owner(e.pid, logger)
        return 1
    except dnf.exceptions.LockError as e:
        logger.critical(e.value)
        return 1
    except IOError as e:
        return ex_IOError(e)
    except KeyboardInterrupt as e:
        print(_("Terminated."), file=sys.stderr)
        return 1
    return 0


def _main(base, args):
    """Run the yum program from a command line interface."""

    dnf.i18n.setup_locale()
    dnf.i18n.setup_stdout()

    # our core object for the cli
    base.logging.presetup()
    cli = dnf.cli.cli.Cli(base)

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        cli.configure(args)
        cli.check()
    except dnf.exceptions.LockError:
        raise
    except dnf.exceptions.Error as e:
        return ex_Error(e)
    except (IOError, OSError) as e:
        return ex_IOError(e)

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
    except dnf.exceptions.Error as e:
        return ex_Error(e)
    except (IOError, OSError) as e:
        return ex_IOError(e)

    if cli.demands.resolving:
        ret = resolving(cli, base)
        if ret:
            return ret

    return cli.demands.success_exit_status


def resolving(cli, base):
    """Perform the depsolve, download and RPM transaction stage."""

    if base.transaction is None:
        logger.info(_('Resolving dependencies'))
        try:
            got_transaction = base.resolve(cli.demands.allow_erasing)
        except dnf.exceptions.Error as e:
            logger.critical(_('Error: %s'), e)
            return 1

        logger.info(_('Dependencies resolved.'))
    else:
        got_transaction = len(base.transaction)

    # Act on the depsolve result
    if not got_transaction:
        logger.info(_('Nothing to do.'))
        persistor = base.group_persistor
        if persistor:
            persistor.commit()
        return 0

    # Run the transaction
    try:
        return_code, resultmsgs = base.do_transaction()
    except dnf.exceptions.LockError:
        raise
    except dnf.exceptions.TransactionCheckError as err:
        return_code, resultmsgs = 1, cli.command.get_error_output(err)
    except dnf.exceptions.Error as e:
        return ex_Error(e)
    except IOError as e:
        return ex_IOError(e)

    # rpm ts.check() failed.
    if resultmsgs:
        for msg in resultmsgs:
            logger.critical("%s", msg)
    elif return_code < 0:
        return_code = 1 # Means the pre-transaction checks failed...
        #  This includes:
        # . No packages.
        # . Hitting N at the prompt.
        # . GPG check failures.
    else:
        base.plugins.run_transaction()
        logger.info(_('Complete!'))

    return return_code


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
