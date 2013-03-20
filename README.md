# DNF

It is a preview of the next major version of Yum [1]. It does package management
using rpm [2] libsolv [3] and hawkey [4] libraries. For metadata handling and
downloads it utilizes librepo library[5].

## Fedora

DNF and all its dependencies are available in Fedora 18, Fedora 19 and the
rawhide Fedora. It is not straightforward, albeit possible, to use DNF with
Fedora 17 and earlier, unless you are able to update rpm and libdb to the Fedora
18 versions first. Might warrant rebuilding rpm database so know what you are
doing and do backup.

[1] http://yum.baseurl.org/  
[2] http://rpm.org/  
[3] https://github.com/openSUSE/libsolv  
[4] https://github.com/akozumpl/hawkey  
[6] https://github.com/tojaj/librepo  
