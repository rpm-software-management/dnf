=============================================
 Comps, or the Ditribution Compose Metadata
=============================================

.. class:: dnf.comps.Comps

  An object of this class can merges comps information from arbitrary repositories. It typically is instantiated from :class:`dnf.Base` and covers all the available repositories.

  The ``*_by_pattern`` methods all take a `pattern` and an optional `case_sensitive` parameter. The pattern is matched against names and IDs of objects in the domain (groups, categories, environments), the globbing characters in `pattern` retain their usual expanding meaning. If `case_sensitive` is ``True``, matching is done in a case-sensitive manner.

  .. attribute:: categories

    List of all contained :class:`dnf.comps.Category` objects.

  .. attribute:: environments

    List of all contained :class:`dnf.comps.Environment` objects.

  .. attribute:: groups

    List of all contained :class:`dnf.comps.Group` objects.

  .. method:: category_by_pattern(pattern, case_sensitive=False)

    Returns a :class:`dnf.comps.Category` object matching `pattern`, or ``None``.

  .. method:: categories_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Category` objects matching `pattern`.

  .. method:: categories_iter

    Return iterator over all contained :class:`dnf.comps.Category` objects.

  .. method:: environment_by_pattern(pattern, case_sensitive=False)

    Return a :class:`dnf.comps.Environment` object matching `pattern`, or ``None``.

  .. method:: environments_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Environment` objects matching `pattern`.

  .. attribute:: environments_iter

    Return iterator over all contained :class:`dnf.comps.Environment` objects.

  .. method:: group_by_pattern(pattern, case_sensitive=False)

    Return a :class:`dnf.comps.Group` object matching `pattern`, or ``None``.

  .. method:: groups_by_pattern(pattern, case_sensitive=False)

    Return an iterable of :class:`dnf.comps.Group` objects matching `pattern`.

  .. attribute:: groups_iter

    Return iterator over all contained :class:`dnf.comps.Group` objects.

.. class:: dnf.comps.Category

  .. attribute:: id

    Unique identifier of the category.

  .. attribute:: name

    Name of the category.

  .. attribute:: ui_name

    The name of the category translated to the language given by the current locale.

  .. attribute:: ui_description

    The description of the category translated to the language given by the current locale.

.. class:: dnf.comps.Environment

    Has the same set of attributes as :class:`dnf.comps.Category`.

.. class:: dnf.comps.Group

    Has the same set of attributes as :class:`dnf.comps.Category`.
