####################################
 Changes in DNF CLI compared to Yum
####################################

.. contents::

======================
 No ``--skip-broken``
======================

The ``--skip-broken`` command line switch is not recognized by DNF. The
semantics this was supposed to trigger in Yum is now the default for plain ``dnf
update``. There is no equivalent for ``yum --skip-broken update foo``, as
silentnly skipping ``foo`` in this case only amounts to masking an error
contradicting the user request. To try using the latest versions of packages in
transactions there is the ``--best`` command line switch.

========================================
Update and Upgrade Commands are the Same
========================================

Invoking ``dnf update`` or ``dnf upgrade``, in all their forms, has the same
effect in DNF, with the latter being preferred. In Yum ``yum upgrade`` was
exactly like ``yum --obsoletes update``.

================================================
 ``clean_requirements_on_remove`` on by default
================================================

The :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
switch is on by default in DNF. It can thus be confusing to compare the "erase"
operation results between DNF and Yum as by default DNF is often going to remove
more packages.

===========================
 No ``resolvedep`` command
===========================

The Yum version of this command is maintained for legacy reasons only. The user
can just do ``dnf provides`` to find out what package gives a particular
provide.
