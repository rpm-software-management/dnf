# DNF

It is a highly experimental replacement for yum [1], evolving from yum's
code. It handles packages using rpm [2] libsolv [3] and hawkey [4] libraries.

## Fedora Users

As of July 2012, DNF and all its dependencies are available in rawhide Fedora
(to be Fedora 18)[5]. It is not straightforward to use DNF with Fedora 17 and
earlier, unless you update rpm and libdb to the Fedora 18 versions first. Might
warrant rebuilding rpm database so know what you are doing and do backup.

[1] http://yum.baseurl.org/
[2] http://rpm.org/
[3] https://github.com/openSUSE/libsolv
[4] https://github.com/akozumpl/hawkey
[5] http://koji.fedoraproject.org/koji/packageinfo?packageID=14310
