..
  Copyright (C) 2014-2018 Red Hat, Inc.

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

========================
Repository Configuration
========================


.. class:: dnf.repodict.RepoDict

  Dictionary mapping repository IDs to the respective :class:`dnf.repo.Repo` objects. Derived from the standard :class:`dict`.

  .. method:: add(repo)

    Add a :class:`.Repo` to the repodict.

  .. method:: add_new_repo(repoid, conf, baseurl=(), \*\*kwargs)

    Initialize new :class:`.Repo` object and add it to the repodict. It requires ``repoid``
    (string), and :class:`dnf.conf.Conf` object. Optionally it can be specified baseurl (list), and
    additionally key/value pairs from `kwargs` to set additional attribute of the :class:`.Repo`
    object. Variables in provided values (``baseurl`` or ``kwargs``) will be automatically
    substituted using conf.substitutions (like ``$releasever``, ...). It returns the :class:`.Repo`
    object.

  .. method:: all()

    Return a list of all contained repositories.

    See the note at :meth:`get_matching` for special semantics of the returned object.

  .. method:: enable_debug_repos()

    Enable debug repos corresponding to already enabled binary repos.

  .. method:: enable_source_repos()

    Enable source repos corresponding to already enabled binary repos.

  .. method:: get_matching(key)

    Return a list of repositories which ID matches (possibly globbed) `key` or an empty list if no matching repository is found.

    The returned list acts as a `composite <http://en.wikipedia.org/wiki/Composite_pattern>`_, transparently forwarding all method calls on itself to the contained repositories. The following thus disables all matching repos::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        repos = base.repos.get_matching('*-debuginfo')
        repos.disable()

  .. method:: iter_enabled()

    Return an iterator over all enabled repos from the dict.

.. module:: dnf.repo

.. function:: repo_id_invalid(repo_id)

  Return index of the first invalid character in the `repo_id` or ``None`` if all characters are valid. This function is used to validate the section names in ``.repo`` files.

.. class:: Metadata

  Represents the metadata files.

  .. attribute:: fresh

    Boolean. ``True`` if the metadata was loaded from the origin, ``False`` if it was loaded from the cache.

.. class:: Repo

  Repository object used for metadata download. To configure it properly one has to give it either :attr:`metalink`, :attr:`mirrorlist` or :attr:`baseurl` parameter.
  This object has attributes corresponding to all configuration options from both :ref:`"Repo Options" <conf_repo_options-label>` and :ref:`"Options for both [main] and Repo" <conf_main_and_repo_options-label>` sections.

  .. IMPORTANT::
    Some :class:`.Repo` attributes return other than Python native types.
    Duck typing works (objects have identical behavior), but isinstance()
    and type() doesn't work as expected because of different types.
    For example :ref:`excludepkgs <exclude-label>` and :ref:`includepkgs <include-label>` return a VectorString, which
    is s SWIG wrapper on top of underlying libdnf C++ code.

  .. attribute:: id

    ID of this repo. This attribute is read-only.

  .. attribute:: metadata

    If :meth:`~load` has been called and succeeded, this contains the relevant :class:`Metadata` instance.

  .. attribute:: pkgdir

    Directory where packages of a remote repo will be downloaded to. By default it is derived from `cachedir` in :meth:`.__init__` but can be overridden by assigning to this attribute.

  .. attribute:: repofile

    The path to configuration file of the class.

  .. method:: __init__(name=None, parent_conf=None)

    Init repository with ID `name` and the `parent_conf` which an instance of :class:`dnf.conf.Conf`
    holding main dnf configuration.

  .. method:: add_metadata_type_to_download(metadata_type)

    Ask for additional repository metadata type to download. Given `metadata_type` is appended to the default metadata set when repository is downloaded.

  .. method:: disable()

    Disable the repository. Repositories are enabled by default.

  .. method:: dump()

    Print repository configuration, including inherited values.

  .. method:: enable()

    Enable the repository (the default).

  .. method:: get_http_headers()

    Return user defined http headers. Return tuple of strings.

  .. method:: get_metadata_content(metadata_type)

    Return content of the file with downloaded repository metadata of given type. Content of compressed metadata file is returned uncompressed.

  .. method:: get_metadata_path(metadata_type)

    Return path to the file with downloaded repository metadata of given type.

  .. method:: load()

    Load the metadata of this repository. Will try to use local cache if possible and initiate and finish download if not. Returns ``True`` if fresh metadata has been downloaded and ``False`` if cache was used. Raises :exc:`dnf.exceptions.RepoError` if the repo metadata could not be obtained.

  .. method:: set_http_headers(headers)

    Set new user headers and rewrite existing ones. `headers` must be an instance of tuple of strings or list of strings.

  .. method:: set_progress_bar(progress)

    Set the download progress reporting object for this repo during :meth:`load`. `progress` must be an instance of :class:`dnf.callback.DownloadProgress`.
