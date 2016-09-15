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

========================
Repository Configuration
========================

.. class:: dnf.repodict.RepoDict

  Dictionary mapping repository IDs to the respective :class:`dnf.repo.Repo` objects. Derived from the standard :class:`dict`.

  .. method:: add(repo)

    Add a :class:`.Repo` to the repodict.

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

  .. attribute:: baseurl

     List of URLs for this repository. Defaults to ``[]``.

  .. attribute:: id

    ID of this repo.

  .. attribute:: metadata

    If :meth:`~load` has been called and succeeded, this contains the relevant :class:`Metadata` instance.

  .. attribute:: metalink

    URL of a metalink for this repository. Defaults to ``None``

  .. attribute:: mirrorlist

    URL of a mirrorlist for this repository. Defaults to ``None``

  .. attribute:: name

    A string with the repo's name. By default it has value of repo's ID.

  .. attribute:: pkgdir

    Directory where packages of a remote repo will be downloaded to. By default it is derived from `cachedir` in :meth:`.__init__` but can be overriden by assigning to this attribute.

  .. attribute:: proxy

    URL of of a proxy server to use when connecting to this repo. Defaults to ``None``, i.e. no proxy used. Also see :attr:`.Conf.proxy`.

  .. attribute:: proxy_username

    The username to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: proxy_password

    The password to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: repofile

    The path to configuration file of the class.

  .. attribute:: skip_if_unavailable

    If enabled, DNF will continue running and disable the repository that couldn't be contacted for any reason when downloading metadata. This option doesn't affect skipping of unavailable packages after dependency resolution. The default is ``True``.

  .. attribute:: sslcacert

    Path to the directory or file containing the certificate authorities to verify SSL certificates.
    Defaults to None - uses system default.

  .. attribute:: sslverify

    Whether SSL certificate checking should be performed at all. Defaults to ``True``.

  .. attribute:: sslclientcert

    Path to the SSL client certificate used to connect to remote sites.
    Defaults to None.

  .. attribute:: sslclientkey

    Path to the SSL client key used to connect to remote sites.
    Defaults to None.

  .. attribute:: username

    The username to use for connecting to repo with basic HTTP authentication. Defaults to ``None``.

  .. attribute:: password

    The password to use for connecting to repo with basic HTTP authentication. Defaults to ``None``.

  .. method:: __init__(name, parent_conf)

    Init repository with ID `name` and the `parent_conf` which an instance of :class:`dnf.conf.Conf`
    holding main dnf configuration.

  .. method:: disable()

    Disable the repository. Repositories are enabled by default.

  .. method:: dump()

    Print repository configuration, including inherited values.

  .. method:: enable()

    Enable the repository (the default).

  .. method:: load()

    Load the metadata of this repository. Will try to use local cache if possible and initiate and finish download if not. Returns ``True`` if fresh metadata has been downloaded and ``False`` if cache was used. Raises :exc:`dnf.exceptions.RepoError` if the repo metadata could not be obtained.

  .. method:: set_progress_bar(progress)

    Set the download progress reporting object for this repo during :meth:`load`. `progress` must be an instance of :class:`dnf.callback.DownloadProgress`.
