# Copyright (C) 2016  Red Hat, Inc.
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import ucd
from dnf.cli.utils import show_lock_owner
from dnf.yum.config import YumConf
from dnf.yum.option_parser import YumOptionParser

import dnf.cli
import dnf.cli.cli
import dnf.cli.main
import dnf.exceptions
import dnf.i18n
import dnf.logging
import dnf.util
import dnf.yum.config
import dnf.yum.cli
import logging
import sys

logger = logging.getLogger("dnf")


def main(args):
    try:
        with dnf.cli.cli.BaseCli(YumConf()) as base:
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
        return dnf.cli.main.ex_Error(e)
    except IOError as e:
        return dnf.cli.main.ex_IOError(e)
    except KeyboardInterrupt as e:
        logger.critical('{}: {}'.format(type(e).__name__, "Terminated."))
        return 1


def _main(base, args):
    """Run the dnf program from a command line interface."""

    dnf.i18n.setup_locale()
    dnf.i18n.setup_stdout()

    # our core object for the cli
    base._logging._presetup()
    cli = dnf.yum.cli.YumCli(base)

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        cli.configure(list(map(ucd, args)), YumOptionParser())
    except dnf.exceptions.LockError:
        raise
    except (IOError, OSError) as e:
        return dnf.cli.main.ex_IOError(e)

    return dnf.cli.main.cli_run(cli, base)


def user_main(args, exit_code=False):
    errcode = main(args)
    if exit_code:
        sys.exit(errcode)
    return errcode
