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

  .. attribute:: releasever

    Used for substitution of ``$releasever`` in the repository configuration.

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