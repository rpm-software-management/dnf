======================
 Queries and Subjects
======================

.. class:: dnf.query.Query

  Facilitates lookup of packages in a :class:`~dnf.sack.Sack` based on given criteria. Query actually does not consult the information in the :class:`~!dnf.sack.Sack` until it is evaluated. The evaluation happens either explicitly using :meth:`~dnf.query.Query.run` or by iterating the query, for example::

    q = base.sack.query()
    i = q.installed()
    i = i.filter(name='pepper')
    packages = list(i) # i only gets evaluated here

    a = q.available()
    a = a.filter(name='pepper')
    for pkg in a: # a only gets evaluated here
        print(pkg.name)

  Notice that none of the filtering methods mutates the state of the :class:`~dnf.query.Query` but produces a new object instead.

  .. method:: available

    Return a new query limiting the original query to the not-installed packages, that is packages available from the repositories.

  .. method:: downgrades

    Return a new query that limits the result only to packages that can be downgrade candidates to other packages in the current set. Downgrade candidate has the same name, lower EVR and the architecture of the original and the downgrade candidate are suitable for a downgrade. Specifically, the filtering does not take any steps to establish that the downgrade candidate can actually be installed.

  .. method:: filter(**kwargs)

    Return a new query limiting the orignal query to the key/value pairs from `kwargs`. Multiple `kwargs` can be passed, the filter then works by applying all of them together (logical AND).

    Allowed keys are:

    ==========   ========== ===============================================
    key          value type value meaning
    ==========   ========== ===============================================
    arch         string     match against packages' architecture
    downgrades   boolean    see :meth:`downgrades`. Defaults to ``False``.
    empty        boolean    ``True`` limits to empty result set.
                            Defaults to ``False``.
    epoch        integer    match against packages' epoch.
    latest       boolean    see :meth:`latest`.  Defaults to ``False``.
    name         string     match against packages' names
    release      string     match against packages' releases
    reponame     string     match against packages repositories' names
    version      string     match against packages' versions
    upgrades     boolean    see :meth:`upgrades`. Defaults to ``False``.
    ==========   ========== ===============================================

  .. method:: installed

    Return a new query that limits the result to the installed packages only.

  .. method:: latest

    Return a new query that limits the result to packages with the highest version per package name and per architecture.

  .. method:: run

    Evaluate the query. Returns a list of matching :class:`dnf.package.Package` instances.

  .. method:: upgrades

    Return a new query that limits the result only to packages that can be upgrade candidates to at least one package in the current set. Upgrade candidate has the same name, higher EVR and the architectures of the original and the upgrade candidate package are suitable for an upgrade. Specifically, the filtering does not take any steps to establish that the upgrade candidate can actually be installed.

.. class:: dnf.subject.Subject

  As :ref:`explained on the DNF man page <specifying_packages-label>`, users of the CLI are able to select packages for an operation in different formats, leaving seemingly arbitrary parts out of the spec and even using globbing characters. This class implements a common approach to parsing such input and produce a :class:`~dnf.query.Query` listing all packages matching the input or a :class:`~dnf.selector.Selector` selecting a single package that best matches the input given a transaction operation.

  .. method:: __init__(pkg_spec, ignore_case=False)

    Initialize the :class:`Subject` with `pkg_spec` input string. If `ignore_case` is ``True`` ignore the case of characters in `pkg_spec`.

  .. method:: get_best_query(sack, with_provides=True, forms=None)

    Return a :class:`~Query` yielding packages matching the given input. The result of the returned query can be an empty set if no package matches. `sack` is the :class:`~dnf.sack.Sack` that the returned query will search. `with_provides` indicates whether besides package names also packages' provides are searched for a match. `forms` is a list of pattern forms from `hawkey`_. Leaving the parameter to ``None`` results in using a reasonable default list of forms.

  .. method:: get_best_selector(sack, forms=None)

    Return a :class:`~dnf.selector.Selector` that will select a single best-matching package when used in a transaction operation. `sack` and `forms` have the same meaning as in :meth:`get_best_query`.

.. module:: dnf.queries
  :deprecated:

.. warning::
   :class:`~dnf.query.Query` and :class:`~dnf.subject.Subject` used to belong in the :mod:`dnf.queries` module. As of dnf-0.4.8 this module is deprecated and will be dropped as early as dnf-0.4.11 (also see :ref:`deprecating-label`).