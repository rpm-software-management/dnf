################
 DNF User's FAQ
################

=============================================================================================================
What to do with packages that DNF refuses to remove because their ``%pre`` or ``%preun`` scripts are failing?
=============================================================================================================

If this happens, it is a packaging error and consider reporting the failure to
the package's maintainer.

You can usually remove such package with ``rpm``::

    rpm -e <package-version> --noscripts
