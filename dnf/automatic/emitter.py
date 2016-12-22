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
            return None
        msg = dnf.pycomp.email_mime(super(EmailEmitter, self)._prepare_msg())
        msg.set_charset('utf-8')
        msg['Date'] = email.utils.formatdate()
        msg['From'] = self._conf.email_from
        msg['Subject'] = subj
        msg['To'] = ','.join(self._conf.email_to)
        msg['Message-ID'] = email.utils.make_msgid()
        return msg.as_string()

    def commit(self):
        # Send the email
        msg = self._prepare_msg()
        if msg is None:
            return
        try:
            smtp = smtplib.SMTP(self._conf.email_host)
            smtp.sendmail(self._conf.email_from, self._conf.email_to, msg)
            smtp.close()
        except smtplib.SMTPException as exc:
            msg = _("Failed to send an email via '%s': %s") % (
                self._conf.email_host, exc)
            logger.error(msg)


class SendmailEmitter(EmailEmitter):
    def commit(self):
        # Send the email
        msg = self._prepare_msg()
        if msg is None:
            return
        cmd = ['/usr/sbin/sendmail', '-bm', '-t']
        try:
            proc = subprocess.Popen(cmd,
                                    universal_newlines=True,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except OSError as e:
            if e.errno == 2:
                logger.error('%s, %s', cmd[0], e.strerror)
            else:
                logger.error('error %d, %s', e.errno, e.strerror)
            return
        out, err = proc.communicate(msg)
        if proc.returncode == 0:
            if out:
                logger.info(out)
            if err:
                logger.error(err)
        else:
            logger.error('error %d, %s', proc.returncode, err)


class StdIoEmitter(Emitter):
    def commit(self):
        msg = self._prepare_msg()
        print(msg)


class MotdEmitter(Emitter):
    def commit(self):
        msg = self._prepare_msg()
        with open('/etc/motd', 'w') as fobj:
            fobj.write(msg)

