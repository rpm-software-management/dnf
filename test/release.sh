#! /bin/sh -e

function bbanner
{
   python -c 'print "=" * 79'
   echo $@
   python -c 'print "-" * 79'
}
function ebanner
{
   python -c 'print "-" * 79'
   echo $@
   python -c 'print "=" * 79'
}


function utst
{
   bbanner "Testing (user):" $@
   $@
   ebanner "Does that look fine? For (user):" $@
   sleep 8
}

function stst
{
   bbanner "Testing (root):" $@
   sudo $@
   ebanner "Does that look fine? For (root):" $@
   sleep 8
}

stst yum version nogroups
utst yum version nogroups
stst yum history list
stst yum history new

utst yum list zzuf

stst yum install zzuf
stst yum reinstall zzuf
stst yum remove zzuf
stst yum install yourmom
stst yum install -y zzuf | tee /tmp/yum-release-testing-install-y-zzuf
stst cat /tmp/yum-release-testing-install-y-zzuf
stst yum remove -y zzuf | tee /tmp/yum-release-testing-remove-y-zzuf
stst cat /tmp/yum-release-testing-remove-y-zzuf

stst yum history list

stst yum localinstall
stst yum localinstall yourmom

stst yum list updates
stst yum list obsoletes
stst yum list available
stst yum list installed
stst yum check-update
# stst yum update

stst yum groupinstall 'News Server'
stst yum groupremove 'News Server'

utst yum grouplist
utst yum grouplist not_a_group
utst yum groupinfo
utst yum groupinfo not_a_group

stst yum info zzuf
utst yum info zzuf
stst yum makecache
utst yum makecache

stst yum clean all
utst yum clean all

stst yum -d0 -e0 install

utst yum --version


stst yum search
utst yum search


stst yum provides zzuf
stst yum provides /usr/bin/zzuf
stst yum provides /usr/bin/yum
utst yum provides /usr/share/man/man1/zzuf.1.gz
utst yum provides '/usr/share/man/man*/zzuf.*.gz'
stst yum provides '/usr/share/man/man1/zzcat.*.gz'
utst yum provides '/usr/share/man/man*/zzcat.*.gz'
utst yum resolvedep /usr/bin/zzcat


stst yum deplist yum
utst yum deplist zzuf


python -c 'print "=" * 79'
python -c 'print "*" * 79'
echo "Done, good to do a release."
python -c 'print "*" * 79'
python -c 'print "=" * 79'
echo "
edit yum/__init__.py __version__ 
edit *.spec versions
git ci
git push

make changelog
git ci
git push

git tag -a yum-#-#-#
git push --tags

stick it in rawhide.

update webpage

upload tarball to yum.baseurl.org:/srv/projects/yum/web/download/x.y

Send email to user and devel mailing list.
"
python -c 'print "=" * 79'
