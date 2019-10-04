..
  Copyright (C) 2019 Red Hat, Inc.

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

=====================
 Modularity Interface
=====================

.. module:: dnf.module.module_base


.. class:: dnf.module.module_base.ModuleBase

Basic class for handling modules.

  .. method:: __init__(base)

    Initialize :class:`dnf.module.module_base.ModuleBase` object. `base` is an instance of the :class:`dnf.Base` class.

  .. method:: enable(module_specs)

    Mark module streams matching the `module_specs` list and also all required modular dependencies for enabling.
    For specs that do not specify the stream, the default stream is used. In case that the module has only one stream available, this stream is used regardles of whether it is the default or not.
    Note that only one stream of any given module can be enabled on a system.
    The method raises :exc:`dnf.exceptions.MarkingErrors` in case of errors.

    Example::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        module_base = dnf.module.module_base.ModuleBase(base)
        module_base.enable(['nodejs:11'])

        base.do_transaction()

  .. method:: disable(module_specs)

    Mark modules matching the `module_specs` list for disabling. Only the name part of the module specification is relevant. Stream, version, context, arch and profile parts are ignored (if given). All streams of the module will be disabled and all installed profiles will be removed. Packages previously installed from these modules will remain installed on the system.
    The method raises :exc:`dnf.exceptions.MarkingErrors` in case of errors.

    Example::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        module_base = dnf.module.module_base.ModuleBase(base)
        module_base.disable(['nodejs'])

        base.do_transaction()

  .. method:: reset(module_specs)

    Mark module for resetting so that it will no longer be enabled or disabled. All installed profiles of streams that have been reset will be removed.
    The method raises :exc:`dnf.exceptions.MarkingErrors` in case of errors.

  .. method:: install(module_specs, strict=True)

    Mark module profiles matching `module_specs` for installation and enable all required streams. If the stream or profile part of specification is not specified, the defaults are chosen. All packages of installed profiles are also marked for installation.
    If `strict` is set to ``False``, the installation skips modules with dependency solving problems.
    The method raises :exc:`dnf.exceptions.MarkingErrors` in case of errors.

    Example::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        module_base = dnf.module.module_base.ModuleBase(base)
        module_base.install(['nodejs:11/minimal'])

        base.resolve()
        base.download_packages(base.transaction.install_set)
        base.do_transaction()

  .. method:: remove(module_specs)

    Mark module profiles matching `module_spec` for removal. All packages installed from removed profiles (unless they are required by other profiles or user-installed packages) are also marked for removal.

  .. method:: upgrade(module_specs)

    Mark packages of module streams (or profiles) matching `module_spec` for upgrade.

  .. method:: get_modules(module_spec)

    Get information about modules matching `module_spec`. Returns tuple (module_packages, nsvcap), where `nsvcap` is a hawkey.NSVCAP object parsed from `module_spec` and `module_packages` is a tuple of :class:`libdnf.module.ModulePackage` objects matching this `nsvcap`.

    Example::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        module_base = dnf.module.module_base.ModuleBase(base)
        module_packages, nsvcap = module_base.get_modules('nodejs:11/minimal')

        print("Parsed NSVCAP:")
        print("name:", nsvcap.name)
        print("stream:", nsvcap.stream)
        print("version:", nsvcap.version)
        print("context:", nsvcap.context)
        print("arch:", nsvcap.arch)
        print("profile:", nsvcap.profile)

        print("Matching modules:")
        for mpkg in module_packages:
            print(mpkg.getFullIdentifier())




.. class:: libdnf.module.ModulePackage

This class represents a record identified by NSVCA from the repository modular metadata. See also https://github.com/fedora-modularity/libmodulemd/blob/master/spec.v2.yaml.

  .. method:: getName()

    Return the name of the module.

  .. method:: getStream()

    Return the stream of the module.

  .. method:: getVersion()

    Return the version of the module as a string.

  .. method:: getVersionNum()

    Return the version of the module as a number.

  .. method:: getContext()

    Return the context of the module.

  .. method:: getArch()

    Return the architecture of the module.

  .. method:: getNameStream()

    Return string in the form of 'name:stream' for the module.

  .. method:: getNameStreamVersion()

    Return string in the form of 'name:stream:version' for the module.

  .. method:: getFullIdentifier()

    Return string in the form of 'name:stream:version:context:architecture' for the module.

  .. method:: getProfiles(name=None)

    Return tuple of :class:`libdnf.module.ModuleProfile` instancies representing each of the individual profiles of the module. If the `name` is given, only profiles matching the `name` pattern are returned.

  .. method:: getSummary()

    Return the summary of the module.

  .. method:: getDescription()

    Return the description of the module.

  .. method:: getRepoID()

    Return the identifier of source repository of the module.

  .. method:: getArtifacts()

    Return tuple of the artifacts of the module.

  .. method:: getModuleDependencies()

    Return tuple of :class:`libdnf.module.ModuleDependencies` objects representing modular dependencies of the module.

  .. method:: getYaml()

    Return repomd yaml representing the module.



.. class:: libdnf.module.ModuleProfile

  .. method:: getName()

    Return the name of the profile.

  .. method:: getDescription()

    Return the description of the profile.

  .. method:: getContent()

    Return tuple of package names to be installed with this profile.



.. class:: libdnf.module.ModuleDependencies

  .. method:: getRequires()

    Return tuple of MapStringVectorString objects. These objects behave like standard python dictionaries and represent individual dependencies of the given module. Keys are names of required modules, values are tuples of required streams specifications.



.. class:: libdnf.module.ModulePackageContainer

    This class is under development and should be considered unstable at the moment.

