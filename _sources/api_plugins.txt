==================
 Plugin Interface
==================

DNF plugin can be any Python class fullfilling the following criteria:

1. it derives from :class:`dnf.Plugin`,
2. it is made available in a Python module stored in one of the :attr:`.Conf.pluginpath`.

When DNF CLI runs it loads the plugins found in the paths during the CLI's initialization.

.. class:: dnf.Plugin

  The base class all DNF plugins must derive from.

  .. method:: __init__(base, cli)

    Plugin must override this. Called immediately after all the plugins are loaded. `base` is an instance of :class:`dnf.Base`.

  .. method:: config

    Plugin can override this. This hook is called immediately after the CLI/extension is finished configuring DNF.  The plugin can use this to tweak the global configuration or the repository configuration.
