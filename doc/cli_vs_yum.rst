####################################
 Changes in DNF CLI compared to Yum
####################################

.. contents::

======================
 No ``--skip-broken``
======================

The ``--skip-broken`` command line switch is not recognized by DNF. The
semantics this was supposed to trigger in Yum is now the default for plain ``dnf
update``. There is now equivalent for ``yum --skip-broken update foo``, as
silentnly skipping ``foo`` in this case only amounts to masking an error
contradicting the user request.

========================================
Update and Upgrade Commands are the Same
========================================

Invoking ``dnf update`` or ``dnf upgrade``, in all their forms, has the same
effect in DNF, with the latter being preferred. In Yum ``yum upgrade`` was
exactly like ``yum --obsoletes update``.
