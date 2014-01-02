========================
Repository Configuration
========================

.. class:: dnf.repodict.RepoDict

  Dictionary mapping repository IDs to the respective :class:`dnf.repo.Repo` objects. Derived from the standard :class:`dict`.

  .. method:: add(repo)

    Add `repo` to the repodict.

  .. method:: iter_enabled()

    Return an iterator over all enabled repos from the dict.

.. module:: dnf.repo

.. function:: repo_id_invalid(repo_id)

  Return index of the first invalid character in the `repo_id` or ``None`` if all characters are valid. This function is used to validate the section names in ``.repo`` files.

.. class:: Repo

  Repository object used for metadata download. To configure it properly one has to give it either :attr:`metalink`, :attr:`mirrorlist` or :attr:`baseurl` parameter.

  .. attribute:: baseurl

     List of URLs for this repository. Defaults to ``[]``.

  .. attribute:: id

    ID of this repo.

  .. attribute:: metalink

    URL of a metalink for this repository. Defaults to ``None``

  .. attribute:: mirrorlist

    URL of a mirrorlist for this repository. Defaults to ``None``

  .. attribute:: name

    A string with the repo's name.

  .. attribute:: sslverify

    Whether SSL certificate checking should be performed at all. Defaults to ``True``.

  .. method:: __init__(id_, cachedir=None)

    Init repository with ID `id_` and using the `cachedir` path for storing downloaded and temporary files.

  .. method:: disable()

    Disable the repository. Repositories are enabled by default.

  .. method:: enable()

    Enable the repository (the default).

  .. method:: load()

    Load the metadata of this repository. Will try to use local cache if possible and initiate and finish download if not. Returns ``True`` if fresh metadata has been downloaded and ``False`` if cache was used. Raises :exc:`dnf.exceptions.RepoError` if the repo metadata could not be obtained.
