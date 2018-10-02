# emitter.py
# Emitters for dnf-automatic.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from dnf.i18n import _
import logging
import dnf.pycomp
import smtplib
import email.utils
import subprocess

APPLIED = _("The following updates have been applied on '%s':")
AVAILABLE = _("The following updates are available on '%s':")
DOWNLOADED = _("The following updates were downloaded on '%s':")

logger = logging.getLogger('dnf')


class Emitter(object):
    def __init__(self, system_name):
        self._applied = False
        self._available_msg = None
        self._downloaded = False
        self._system_name = system_name
        self._trans_msg = None

    def _prepare_msg(self):
        msg = []
        if self._applied:
            msg.append(APPLIED % self._system_name)
            msg.append(self._available_msg)
        elif self._downloaded:
            msg.append(DOWNLOADED % self._system_name)
            msg.append(self._available_msg)
        elif self._available_msg:
            msg.append(AVAILABLE % self._system_name)
            msg.append(self._available_msg)
        else:
            return None
        return '\n'.join(msg)

    def notify_applied(self):
        assert self._available_msg
        self._applied = True

    def notify_available(self, msg):
        self._available_msg = msg

    def notify_downloaded(self):
        assert self._available_msg
        self._downloaded = True


class EmailEmitter(Emitter):
    def __init__(self, system_name, conf):
        super(EmailEmitter, self).__init__(system_name)
        self._conf = conf

    def _prepare_msg(self):
        if self._applied:
            subj = _("Updates applied on '%s'.") % self._system_name
        elif self._downloaded:
            subj = _("Updates downloaded on '%s'.") % self._system_name
        elif self._available_msg:
            subj = _("Updates available on '%s'.") % self._system_name
        else:
            return None, None
        return subj, super(EmailEmitter, self)._prepare_msg()

    def commit(self):
        subj, body = self._prepare_msg()
        message = dnf.pycomp.email_mime(body)
        message.set_charset('utf-8')
        email_from = self._conf.email_from
        email_to = self._conf.email_to
        message['Date'] = email.utils.formatdate()
        message['From'] = email_from
        message['Subject'] = subj
        message['To'] = ','.join(email_to)
        message['Message-ID'] = email.utils.make_msgid()

        # Send the email
        try:
            smtp = smtplib.SMTP(self._conf.email_host, timeout=300)
            smtp.sendmail(email_from, email_to, message.as_string())
            smtp.close()
        except smtplib.SMTPException as exc:
            msg = _("Failed to send an email via '%s': %s") % (
                self._conf.email_host, exc)
            logger.error(msg)


class CommandEmitterMixIn(object):
    """
    Executes a desired command, and pushes data into its stdin.
    Both data and command can be formatted according to user preference.
    For this reason, this class expects a {str:str} dictionary as _prepare_msg
    return value.
    Meant for mixing with Emitter classes, as it does not define any names used
    for formatting on its own.
    """
    def commit(self):
        command_fmt = self._conf.command_format
        stdin_fmt = self._conf.stdin_format
        msg = self._prepare_msg()
        # all strings passed to shell should be quoted to avoid accidental code
        # execution
        quoted_msg = dict((key, dnf.pycomp.shlex_quote(val))
                          for key, val in msg.items())
        command = command_fmt.format(**quoted_msg)
        stdin_feed = stdin_fmt.format(**msg).encode('utf-8')

        # Execute the command
        subp = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE)
        subp.communicate(stdin_feed)
        subp.stdin.close()
        if subp.wait() != 0:
            msg = _("Failed to execute command '%s': returned %d") \
                  % (command, subp.returncode)
            logger.error(msg)


class CommandEmitter(CommandEmitterMixIn, Emitter):
    def _prepare_msg(self):
        return {'body': super(CommandEmitter, self)._prepare_msg()}


class CommandEmailEmitter(CommandEmitterMixIn, EmailEmitter):
    def _prepare_msg(self):
        subject, body = super(CommandEmailEmitter, self)._prepare_msg()
        return {'subject': subject,
                'body': body,
                'email_from': self._conf.email_from,
                'email_to': ' '.join(self._conf.email_to)}


class StdIoEmitter(Emitter):
    def commit(self):
        msg = self._prepare_msg()
        print(msg)


class MotdEmitter(Emitter):
    def commit(self):
        msg = self._prepare_msg()
        with open('/etc/motd', 'w') as fobj:
            fobj.write(msg)

