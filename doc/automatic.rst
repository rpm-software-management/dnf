..
  Copyright (C) 2014-2016 Red Hat, Inc.

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

###############
 DNF Automatic
###############

==========
 Synopsis
==========

``dnf-automatic [<config file>]``

=============
 Description
=============

Alternative CLI to ``dnf upgrade`` with specific facilities to make it suitable to be executed automatically and regularly from systemd timers, cron jobs and similar.

The operation of the tool is completely controlled by the configuration file and the command only accepts single optional argument pointing to it. If no configuration file is passed from the command line, ``/etc/dnf/automatic.conf`` is used.

The tool synchronizes package metadata as needed and then checks for updates available for the given system and then either exits, downloads the packages or downloads and applies the packages. The outcome of the operation is then reported by a selected mechanism, for instance via the standard output, email or motd messages.

A few default systemd units are provided to enable some standard configurations:

- dnf-automatic-notifyonly
- dnf-automatic-download
- dnf-automatic-install

===================
 Run dnf-automatic
===================

You can select on that most closely fits your needs, customize ``/etc/dnf/automatic.conf`` for any specific behaviors, and enable the timer unit.

For example:``systemctl enable dnf-automatic-notifyonly.timer && systemctl start dnf-automatic-notifyonly.timer``

===========================
 Configuration File Format
===========================

The configuration file is separated into topical sections.

---------------------
``[commands]`` section
---------------------

Setting the mode of operation of the program.

``apply_updates``
    boolean, default: False

    Whether packages comprising the available should be applied (i.e. installed via RPM). Implies ``download_updates``. Note that if this is set to ``False``, downloaded packages will be left in the cache to the next successful DNF transaction.

``download_updates``
    boolean, default: False

    Whether packages comprising the available should be downloaded.

.. _upgrade_type_automatic-label:

``upgrade_type``
    either one of ``default``, ``security``, default: ``default``

    What kind of upgrades to look at. ``default`` signals looking for all available updates, ``security`` only those with an  issued security advisory.

``random_sleep``
    time in seconds, default: 300

    Maximal random delay before downloading.

----------------------
``[emitters]`` section
----------------------

Choosing how the results should be reported.

.. _emit_via_automatic-label:

``emit_via``
    list, default: ``email, stdio, motd``

    List of emitters to report the results through. Available emitters are ``stdio`` to print the result to standard output, ``email`` to send the report via email and ``motd`` sends the result to */etc/motd* file.

``system_name``
    string, default: hostname of the given system

    How the system is called in the reports.

-------------------
``[email]`` section
-------------------

The email emitter configuration.

``email_from``
    string, default: ``root``

    Message's "From:" address.

``email_to``
    list, default: ``root``

    List of recipients of the message.

``email_host``
    string, default: ``localhost``

    Hostname of the SMTP server used to send the message.

------------------
``[base]`` section
------------------

Can be used to override settings from DNF's main configuration file. See :doc:`conf_ref`.

