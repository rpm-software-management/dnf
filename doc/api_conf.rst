..
  Copyright (C) 2014  Red Hat, Inc.

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

===============
 Configuration
===============

Configurable settings of the :class:`dnf.Base` object are stored into a :class:`dnf.conf.Conf` instance. The various options are described here.

.. class:: dnf.conf.Conf

  .. attribute:: best

    Boolean option, ``True`` instructs the solver to either use a package with the highest available version or fail. On ``False``, do not fail if the latest version can not be installed. Default is ``False``.

  .. attribute:: cachedir

    Path to a directory used by various DNF subsystems for storing cache data. Has a reasonable root-writable default depending on the distribution. It is up to the client to set this to a location where files and directories can be created under the running user. The directory can be safely deleted after the :class:`dnf.Base` object is destroyed

  .. attribute:: config_file_path

    Path to the default main configuration file. Default is ``"/etc/dnf/dnf.conf"``.

  .. attribute:: debuglevel

    Debug messages output level, in the range 0 to 10. Default is 2.

  .. attribute:: installonly_limit

    An integer to limit the number of installed installonly packages (packages that do not upgrade, instead few versions are installed in parallel). Defaults to ``0``, that is the limiting is disabled.

  .. attribute:: installroot

    The root of the filesystem for all packaging operations.

  .. attribute:: logdir

    Directory where the log files will be stored. Default is ``"/var/log"``.

  .. attribute:: multilib_policy

    Controls how multilib packages are treated during install operations. Can either be ``"best"`` (the default) for the depsolver to prefer packages which best match the system's architecture, or ``"all"`` to install all available packages with compatible architectures.

  .. attribute:: persistdir

    Directory where the data that DNF keeps track of between different runs is stored. Default is ``"/var/lib/dnf"``.

  .. attribute:: pluginpath

    List of directories where DNF searches for :doc:`plugins <api_plugins>`. The default contains a Python version-specific path.

  .. attribute:: proxy

    URL of of a proxy server to use for network connections. Defaults to ``None``, i.e. no proxy used. The expected format of this option is::

      <scheme>://<ip-or-hostname>[:port]

  .. attribute:: proxy_username

    The username to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: proxy_password

    The password to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: releasever

    Used for substitution of ``$releasever`` in the repository configuration.

  .. attribute:: reposdir

    List of directories to search for repo configuration files. Has a reasonable default commonly used on the given distribution.

  .. attribute:: substitutions

    A mapping of substitutions used in repositories' remote URL configuration. The commonly used ones are:

    ==========     ============================================== ============
    key            meaning                                        default
    ==========     ============================================== ============
    arch           architecture of the machine                    autodetected
    basearch       the architecture family of the current "arch"  autodetected
    releasever     release name of the system distribution        ``None``
    ==========     ============================================== ============

    :func:`dnf.rpm.detect_releasever` can be used to detect the ``releasever`` value.

  .. attribute:: tsflags

    List of strings adding extra flags for the RPM transaction.

    ==========              ===========================
    tsflag                  RPM Transaction Flag
    ==========              ===========================
    noscripts               RPMTRANS_FLAG_NOSCRIPTS
    test                    RPMTRANS_FLAG_TEST
    notriggers              RPMTRANS_FLAG_NOTRIGGERS
    nodocs                  RPMTRANS_FLAG_NODOCS
    justdb                  RPMTRANS_FLAG_JUSTDB
    nocontexts              RPMTRANS_FLAG_NOCONTEXTS
    nocrypto                RPMTRANS_FLAG_NOFILEDIGEST
    ==========              ===========================

    The ``"nocrypto"`` option will also set the ``_RPMVSF_NOSIGNATURES`` and ``_RPMVSF_NODIGESTS`` VS flags.

  .. method:: prepend_installroot(option)

    Prefix config option named `option` with :attr:`installroot`.

  .. method:: read(filename=None)

    Read configuration options from the ``main`` section in `filename`. Option values not present there are left at their current values. If `filename` is ``None``, :attr:`config_file_path` is used. Conversely, the configuration path used to load the configuration file that was used is stored into :attr:`config_file_path` before the function returns.