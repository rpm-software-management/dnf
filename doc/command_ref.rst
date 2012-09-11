#######################
 DNF Command Reference
#######################

========
Synopsis
========

``dnf [options] <command> <[args]>``

===========
Description
===========

`DNF`_ is an experimental replacent for `Yum`_, a package manager for RPM Linux
distributions. It aims to maintain CLI compatibility with Yum while improving on
speed and defining strict API and plugin interface.


Available commands are:

* downgrade
* erase
* help
* history
* info
* install
* list
* makecache
* provides
* repolist
* update

See the reference for each command below.

=======
Options
=======

``-h, --help``
    Shows the help.

``-C, --cacheonly``
    Run entirely from system cache, don't update cache

``-c [config file], --config=[config file]``
    config file location

``-R [minutes], --randomwait=[minutes]``
    maximum command wait time

``-d [debug level], --debuglevel=[debug level]``
    debugging output level

``--showduplicates``
    show duplicates, in repos, in list/search commands

``-e [error level], --errorlevel=[error level]``
    error output level

``--rpmverbosity=[debug level name]``
    debugging output level for rpm

``-q, --quiet``
    quiet operation

``-v, --verbose``
    verbose operation

``-y, --assumeyes``
    answer yes for all questions

``--assumeno``
    answer no for all questions

``--version``
    show Yum version and exit

``--installroot=[path]``
    set install root

========
See Also
========

* `DNF`_ project homepage (https://github.com/akozumpl/dnf/)
* `Yum`_ project homepage (http://yum.baseurl.org/)
