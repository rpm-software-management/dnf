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

=====================================================================================================
Why are ``dnf check-update`` packages not marked for upgrade in the following ``dnf upgrade``
=====================================================================================================

Sometimes one can see that a newer version of a package is available in the repos::

    $ dnf check-update
    libocsync0.x86_64 0.91.4-2.1              devel_repo
    owncloud-client.x86_64 1.5.0-18.1         devel_repo

Yet the immediately following ``dnf upgrade`` does not offer them for upgrade::

    $ dnf upgrade
    Resolving dependencies
    --> Starting dependency resolution
    --> Finished dependency resolution
    Dependencies resolved.
    Nothing to do.

It might seem odd but in fact this can happen quite easily: what the first command does is only check whether there are some available packages with the same name as an installed package but with a higher version. Those are considered upgrade candidates by ``check-update``, but no actual dependency resolving takes place there. That only happens during ``dnf upgrade`` and if the resolving procedure then discovers that some of the packages do not have their dependencies ready yet, then they are not offered in the upgrade. To see the precise reason why it was not possible to do the upgrade in this case, use::

    $ dnf upgrade --best

=====================================================================
Why do I get different results with ``dnf update`` vs ``yum update``?
=====================================================================

We get this reported as a bug quite often, but it usually is not. One reason to see this is that DNF does not list update candidates as it explores them. More frequently however the reporter means actual difference in the proposed transaction. This is most often because the metadata the two packagers are working with were taken at a different time (DNF has a notoriously looser schedule on metadata updates to save time and bandwidth), and sometimes also because the depsolvers inside are designed to take a different course of action when encountering some specific update scenario.

The bottom line is: unless a real update problem occurs (i.e. DNF refuses to update a package that Yum updates) with the same set of metadata, this is not an issue.
