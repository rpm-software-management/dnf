# Copyright 2006 Duke University
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import libdnf

from dnf.i18n import _, ucd
from dnf.cli import commands
import dnf.cli
import dnf.exceptions
import dnf.transaction
import dnf.util

import logging
import os


logger = logging.getLogger('dnf')


class HistoryCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    history command.
    """

    aliases = ('history', 'hist')
    summary = _('display, or use, the transaction history')

    _CMDS = ['list', 'info', 'redo', 'rollback', 'undo', 'userinstalled']

    transaction_ids = set()
    merged_transaction_ids = set()

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('transactions_action', nargs='?', metavar="COMMAND",
                            help="Available commands: {} (default), {}".format(
                                HistoryCommand._CMDS[0],
                                ", ".join(HistoryCommand._CMDS[1:])))
        parser.add_argument('--reverse', action='store_true',
                            help="display history list output reversed")
        parser.add_argument('transactions', nargs='*', metavar="TRANSACTION",
                            help="Transaction ID (<number>, 'last' or 'last-<number>' "
                                 "for one transaction, <transaction-id>..<transaction-id> "
                                 "for range)")

    def configure(self):
        if not self.opts.transactions_action:
            # no positional argument given
            self.opts.transactions_action = self._CMDS[0]
        elif self.opts.transactions_action not in self._CMDS:
            # first positional argument is not a command
            self.opts.transactions.insert(0, self.opts.transactions_action)
            self.opts.transactions_action = self._CMDS[0]

        require_one_transaction_id = False
        require_one_transaction_id_msg = _("Found more than one transaction ID.\n"
                                           "'{}' requires one transaction ID or package name."
                                           ).format(self.opts.transactions_action)
        demands = self.cli.demands
        if self.opts.transactions_action in ['redo', 'undo', 'rollback']:
            demands.root_user = True
            require_one_transaction_id = True
            if not self.opts.transactions:
                msg = _('No transaction ID or package name given.')
                logger.critical(msg)
                raise dnf.cli.CliError(msg)
            elif len(self.opts.transactions) > 1:
                logger.critical(require_one_transaction_id_msg)
                raise dnf.cli.CliError(require_one_transaction_id_msg)
            demands.available_repos = True
            commands._checkGPGKey(self.base, self.cli)
        else:
            demands.fresh_metadata = False
        demands.sack_activation = True
        if self.base.history.path != ":memory:" and not os.access(self.base.history.path, os.R_OK):
            msg = _("You don't have access to the history DB: %s" % self.base.history.path)
            logger.critical(msg)
            raise dnf.cli.CliError(msg)
        self.transaction_ids = self._args2transaction_ids(self.merged_transaction_ids,
                                                          require_one_transaction_id,
                                                          require_one_transaction_id_msg)

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            if self.opts.transactions_action == 'undo':
                id_, = self.opts.transactions
                return (_('Cannot undo transaction %s, doing so would result '
                          'in an inconsistent package database.') % id_,)
            elif self.opts.transactions_action == 'rollback':
                id_, = (self.opts.transactions if self.opts.transactions[0] != 'force'
                        else self.opts.transactions[1:])
                return (_('Cannot rollback transaction %s, doing so would '
                          'result in an inconsistent package database.') % id_,)

        return dnf.cli.commands.Command.get_error_output(self, error)

    def _hcmd_redo(self, extcmds):
        old = self.base.history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history redo']
        tm = dnf.util.normalize_time(old.beg_timestamp)
        print('Repeating transaction %u, from %s' % (old.tid, tm))
        self.output.historyInfoCmdPkgsAltered(old)

        for i in old.packages():
            pkgs = list(self.base.sack.query().filter(nevra=str(i), reponame=i.from_repo))
            if i.action in dnf.transaction.FORWARD_ACTIONS:
                if not pkgs:
                    logger.info(_('No package %s available.'),
                    self.output.term.bold(ucd(str(i))))
                    return 1, ['An operation cannot be redone']
                pkg = pkgs[0]
                self.base.install(str(pkg))
            elif i.action == libdnf.transaction.TransactionItemAction_REMOVE:
                if not pkgs:
                    # package was removed already, we can skip removing it again
                    continue
                pkg = pkgs[0]
                self.base.remove(str(pkg))

        self.base.resolve()
        self.base.do_transaction()

    def _hcmd_undo(self, extcmds):
        try:
            return self.base.history_undo_transaction(extcmds[0])
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_rollback(self, extcmds):
        try:
            return self.base.history_rollback_transaction(extcmds[0])
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_userinstalled(self):
        """Execute history userinstalled command."""
        pkgs = tuple(self.base.iter_userinstalled())
        return self.output.listPkgs(pkgs, 'Packages installed by user', 'nevra')

    def _args2transaction_ids(self, merged_ids=set(),
                              require_one_trans_id=False, require_one_trans_id_msg=''):
        """Convert commandline arguments to transaction ids"""

        def str2transaction_id(s):
            if s == 'last':
                s = '0'
            elif s.startswith('last-'):
                s = s[4:]
            transaction_id = int(s)
            if transaction_id <= 0:
                transaction_id += self.output.history.last().tid
            return transaction_id

        transaction_ids = set()
        for t in self.opts.transactions:
            if '..' in t:
                try:
                    begin_transaction_id, end_transaction_id = t.split('..', 2)
                except ValueError:
                    logger.critical(
                        _("Invalid transaction ID range definition '{}'.\n"
                          "Use '<transaction-id>..<transaction-id>'."
                          ).format(t))
                    raise dnf.cli.CliError
                cant_convert_msg = _("Can't convert '{}' to transaction ID.\n"
                                     "Use '<number>', 'last', 'last-<number>'.")
                try:
                    begin_transaction_id = str2transaction_id(begin_transaction_id)
                except ValueError:
                    logger.critical(_(cant_convert_msg).format(begin_transaction_id))
                    raise dnf.cli.CliError
                try:
                    end_transaction_id = str2transaction_id(end_transaction_id)
                except ValueError:
                    logger.critical(_(cant_convert_msg).format(end_transaction_id))
                    raise dnf.cli.CliError
                if require_one_trans_id and begin_transaction_id != end_transaction_id:
                        logger.critical(require_one_trans_id_msg)
                        raise dnf.cli.CliError
                if begin_transaction_id > end_transaction_id:
                    begin_transaction_id, end_transaction_id = \
                        end_transaction_id, begin_transaction_id
                merged_ids.add((begin_transaction_id, end_transaction_id))
                transaction_ids.update(range(begin_transaction_id, end_transaction_id + 1))
            else:
                try:
                    transaction_ids.add(str2transaction_id(t))
                except ValueError:
                    # not a transaction id, assume it's package name
                    transact_ids_from_pkgname = self.output.history.search([t])
                    if transact_ids_from_pkgname:
                        transaction_ids.update(transact_ids_from_pkgname)
                    else:
                        msg = _("No transaction which manipulates package '{}' was found."
                                ).format(t)
                        if require_one_trans_id:
                            logger.critical(msg)
                            raise dnf.cli.CliError
                        else:
                            logger.info(msg)

        return sorted(transaction_ids, reverse=True)

    def run(self):
        vcmd = self.opts.transactions_action

        ret = None
        if vcmd == 'list' and (self.transaction_ids or not self.opts.transactions):
            ret = self.output.historyListCmd(self.transaction_ids,
                reverse=self.opts.reverse)
        elif vcmd == 'info' and (self.transaction_ids or not self.opts.transactions):
            ret = self.output.historyInfoCmd(self.transaction_ids, self.opts.transactions,
                                             self.merged_transaction_ids)
        elif vcmd == 'undo':
            ret = self._hcmd_undo(self.transaction_ids)
        elif vcmd == 'redo':
            ret = self._hcmd_redo(self.transaction_ids)
        elif vcmd == 'rollback':
            ret = self._hcmd_rollback(self.transaction_ids)
        elif vcmd == 'userinstalled':
            ret = self._hcmd_userinstalled()

        if ret is None:
            return
        (code, strs) = ret
        if code == 2:
            self.cli.demands.resolving = True
        elif code != 0:
            raise dnf.exceptions.Error(strs[0])
