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
import hawkey

from dnf.i18n import _, ucd
from dnf.cli import commands
from dnf.transaction_sr import TransactionReplay, serialize_transaction

import dnf.cli
import dnf.exceptions
import dnf.transaction
import dnf.util

import json
import logging
import os


logger = logging.getLogger('dnf')


class HistoryCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    history command.
    """

    aliases = ('history', 'hist')
    summary = _('display, or use, the transaction history')

    _CMDS = ['list', 'info', 'redo', 'replay', 'rollback', 'store', 'undo', 'userinstalled']

    def __init__(self, *args, **kw):
        super(HistoryCommand, self).__init__(*args, **kw)

        self._require_one_transaction_id = False

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('transactions_action', nargs='?', metavar="COMMAND",
                            help="Available commands: {} (default), {}".format(
                                HistoryCommand._CMDS[0],
                                ", ".join(HistoryCommand._CMDS[1:])))
        parser.add_argument('--reverse', action='store_true',
                            help="display history list output reversed")
        parser.add_argument("-o", "--output", default=None,
                            help=_("For the store command, file path to store the transaction to"))
        parser.add_argument("--ignore-installed", action="store_true",
                            help=_("For the replay command, don't check for installed packages matching "
                            "those in transaction"))
        parser.add_argument("--ignore-extras", action="store_true",
                            help=_("For the replay command, don't check for extra packages pulled "
                            "into the transaction"))
        parser.add_argument("--skip-unavailable", action="store_true",
                            help=_("For the replay command, skip packages that are not available or have "
                            "missing dependencies"))
        parser.add_argument('transactions', nargs='*', metavar="TRANSACTION",
                            help="For commands working with history transactions, "
                                 "Transaction ID (<number>, 'last' or 'last-<number>' "
                                 "for one transaction, <transaction-id>..<transaction-id> "
                                 "for a range)")
        parser.add_argument('transaction_filename', nargs='?', metavar="TRANSACTION_FILE",
                            help="For the replay command, path to the stored "
                                 "transaction file to replay")

    def configure(self):
        if not self.opts.transactions_action:
            # no positional argument given
            self.opts.transactions_action = self._CMDS[0]
        elif self.opts.transactions_action not in self._CMDS:
            # first positional argument is not a command
            self.opts.transactions.insert(0, self.opts.transactions_action)
            self.opts.transactions_action = self._CMDS[0]

        self._require_one_transaction_id_msg = _("Found more than one transaction ID.\n"
                                                 "'{}' requires one transaction ID or package name."
                                                 ).format(self.opts.transactions_action)

        demands = self.cli.demands
        if self.opts.transactions_action == 'replay':
            if not self.opts.transactions:
                raise dnf.cli.CliError(_('No transaction file name given.'))
            if len(self.opts.transactions) > 1:
                raise dnf.cli.CliError(_('More than one argument given as transaction file name.'))

            # in case of replay, copy over the file name to it's appropriate variable
            # (the arg parser can't distinguish here)
            self.opts.transaction_filename = os.path.abspath(self.opts.transactions[0])
            self.opts.transactions = []

            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

            # Override configuration options that affect how the transaction is resolved
            self.base.conf.clean_requirements_on_remove = False
            self.base.conf.install_weak_deps = False

            dnf.cli.commands._checkGPGKey(self.base, self.cli)
        elif self.opts.transactions_action == 'store':
            self._require_one_transaction_id = True
            if not self.opts.transactions:
                raise dnf.cli.CliError(_('No transaction ID or package name given.'))
        elif self.opts.transactions_action in ['redo', 'undo', 'rollback']:
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

            self._require_one_transaction_id = True
            if not self.opts.transactions:
                msg = _('No transaction ID or package name given.')
                logger.critical(msg)
                raise dnf.cli.CliError(msg)
            elif len(self.opts.transactions) > 1:
                logger.critical(self._require_one_transaction_id_msg)
                raise dnf.cli.CliError(self._require_one_transaction_id_msg)
            demands.available_repos = True
            dnf.cli.commands._checkGPGKey(self.base, self.cli)
        else:
            demands.fresh_metadata = False
        demands.sack_activation = True
        if self.base.history.path != ":memory:" and not os.access(self.base.history.path, os.R_OK):
            msg = _("You don't have access to the history DB: %s" % self.base.history.path)
            logger.critical(msg)
            raise dnf.cli.CliError(msg)

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
        old = self._history_get_transaction(extcmds)
        data = serialize_transaction(old)
        self.replay = TransactionReplay(
            self.base,
            data=data,
            ignore_installed=True,
            ignore_extras=True,
            skip_unavailable=self.opts.skip_unavailable
        )
        self.replay.run()

    def _history_get_transactions(self, extcmds):
        if not extcmds:
            raise dnf.cli.CliError(_('No transaction ID given'))

        old = self.base.history.old(extcmds)
        if not old:
            raise dnf.cli.CliError(_('Transaction ID "{0}" not found.').format(extcmds[0]))
        return old

    def _history_get_transaction(self, extcmds):
        old = self._history_get_transactions(extcmds)
        if len(old) > 1:
            raise dnf.cli.CliError(_('Found more than one transaction ID!'))
        return old[0]

    def _hcmd_undo(self, extcmds):
        old = self._history_get_transaction(extcmds)
        self._revert_transaction(old)

    def _hcmd_rollback(self, extcmds):
        old = self._history_get_transaction(extcmds)
        last = self.base.history.last()

        merged_trans = None
        if old.tid != last.tid:
            # history.old([]) returns all transactions and we don't want that
            # so skip merging the transactions when trying to rollback to the last transaction
            # which is the current system state and rollback is not applicable
            for trans in self.base.history.old(list(range(old.tid + 1, last.tid + 1))):
                if trans.altered_lt_rpmdb:
                    logger.warning(_('Transaction history is incomplete, before %u.'), trans.tid)
                elif trans.altered_gt_rpmdb:
                    logger.warning(_('Transaction history is incomplete, after %u.'), trans.tid)

                if merged_trans is None:
                    merged_trans = dnf.db.history.MergedTransactionWrapper(trans)
                else:
                    merged_trans.merge(trans)

        self._revert_transaction(merged_trans)

    def _revert_transaction(self, trans):
        action_map = {
            "Install": "Removed",
            "Removed": "Install",
            "Upgrade": "Downgraded",
            "Upgraded": "Downgrade",
            "Downgrade": "Upgraded",
            "Downgraded": "Upgrade",
            "Reinstalled": "Reinstall",
            "Reinstall": "Reinstalled",
            "Obsoleted": "Install",
            "Obsolete": "Obsoleted",
            "Reason Change": "Reason Change",
        }

        data = serialize_transaction(trans)

        # revert actions in the serialized transaction data to perform rollback/undo
        for content_type in ("rpms", "groups", "environments"):
            for ti in data.get(content_type, []):
                ti["action"] = action_map[ti["action"]]

                if ti["action"] == "Install" and ti.get("reason", None) == "clean":
                    ti["reason"] = "dependency"

                if ti["action"] == "Reason Change" and "nevra" in ti:
                    subj = hawkey.Subject(ti["nevra"])
                    nevra = subj.get_nevra_possibilities(forms=[hawkey.FORM_NEVRA])[0]
                    reason = self.output.history.swdb.resolveRPMTransactionItemReason(
                        nevra.name,
                        nevra.arch,
                        trans.tids()[0] - 1
                    )
                    ti["reason"] = libdnf.transaction.TransactionItemReasonToString(reason)

                if ti.get("repo_id") == hawkey.SYSTEM_REPO_NAME:
                    # erase repo_id, because it's not possible to perform forward actions from the @System repo
                    ti["repo_id"] = None

        self.replay = TransactionReplay(
            self.base,
            data=data,
            ignore_installed=True,
            ignore_extras=True,
            skip_unavailable=self.opts.skip_unavailable
        )
        self.replay.run()

    def _hcmd_userinstalled(self):
        """Execute history userinstalled command."""
        pkgs = tuple(self.base.iter_userinstalled())
        n_listed = self.output.listPkgs(pkgs, 'Packages installed by user', 'nevra')
        if n_listed == 0:
            raise dnf.cli.CliError(_('No packages to list'))

    def _args2transaction_ids(self):
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

        tids = set()
        merged_tids = set()
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
                if self._require_one_transaction_id and begin_transaction_id != end_transaction_id:
                        logger.critical(self._require_one_transaction_id_msg)
                        raise dnf.cli.CliError
                if begin_transaction_id > end_transaction_id:
                    begin_transaction_id, end_transaction_id = \
                        end_transaction_id, begin_transaction_id
                merged_tids.add((begin_transaction_id, end_transaction_id))
                tids.update(range(begin_transaction_id, end_transaction_id + 1))
            else:
                try:
                    tids.add(str2transaction_id(t))
                except ValueError:
                    # not a transaction id, assume it's package name
                    transact_ids_from_pkgname = self.output.history.search([t])
                    if transact_ids_from_pkgname:
                        tids.update(transact_ids_from_pkgname)
                    else:
                        msg = _("No transaction which manipulates package '{}' was found."
                                ).format(t)
                        if self._require_one_transaction_id:
                            logger.critical(msg)
                            raise dnf.cli.CliError
                        else:
                            logger.info(msg)

        return sorted(tids, reverse=True), merged_tids

    def run(self):
        vcmd = self.opts.transactions_action

        if vcmd == 'replay':
            self.replay = TransactionReplay(
                self.base,
                filename=self.opts.transaction_filename,
                ignore_installed = self.opts.ignore_installed,
                ignore_extras = self.opts.ignore_extras,
                skip_unavailable = self.opts.skip_unavailable
            )
            self.replay.run()
        else:
            tids, merged_tids = self._args2transaction_ids()

            if vcmd == 'list' and (tids or not self.opts.transactions):
                self.output.historyListCmd(tids, reverse=self.opts.reverse)
            elif vcmd == 'info' and (tids or not self.opts.transactions):
                self.output.historyInfoCmd(tids, self.opts.transactions, merged_tids)
            elif vcmd == 'undo':
                self._hcmd_undo(tids)
            elif vcmd == 'redo':
                self._hcmd_redo(tids)
            elif vcmd == 'rollback':
                self._hcmd_rollback(tids)
            elif vcmd == 'userinstalled':
                self._hcmd_userinstalled()
            elif vcmd == 'store':
                tid = self._history_get_transaction(tids)
                data = serialize_transaction(tid)
                try:
                    filename = self.opts.output if self.opts.output is not None else "transaction.json"

                    # it is absolutely possible for both assumeyes and assumeno to be True, go figure
                    if (self.base.conf.assumeno or not self.base.conf.assumeyes) and os.path.isfile(filename):
                        msg = _("{} exists, overwrite?").format(filename)
                        if self.base.conf.assumeno or not self.base.output.userconfirm(
                            msg='\n{} [y/N]: '.format(msg), defaultyes_msg='\n{} [Y/n]: '.format(msg)):
                                print(_("Not overwriting {}, exiting.").format(filename))
                                return

                    with open(filename, "w") as f:
                        json.dump(data, f, indent=4, sort_keys=True)
                        f.write("\n")

                    print(_("Transaction saved to {}.").format(filename))

                except OSError as e:
                    raise dnf.cli.CliError(_('Error storing transaction: {}').format(str(e)))

    def run_resolved(self):
        if self.opts.transactions_action not in ("replay", "redo", "rollback", "undo"):
            return

        self.replay.post_transaction()

    def run_transaction(self):
        if self.opts.transactions_action not in ("replay", "redo", "rollback", "undo"):
            return

        warnings = self.replay.get_warnings()
        if warnings:
            logger.log(
                dnf.logging.WARNING,
                _("Warning, the following problems occurred while running a transaction:")
            )
            for w in warnings:
                logger.log(dnf.logging.WARNING, "  " + w)
