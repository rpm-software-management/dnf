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
   "$@"
   ebanner "Does that look fine? For (user):" $@
   sleep 8
}

function stst
{
   bbanner "Testing (root):" $@
   sudo "$@"
   ebanner "Does that look fine? For (root):" $@
   sleep 8
}

stst yum version nogroups
utst yum version nogroups
stst yum history list
stst yum history new
stst yum history new

utst yum list zzuf

stst yum version nogroups
stst yum install zzuf
stst yum version nogroups
stst yum reinstall zzuf
stst yum version nogroups
stst yum remove zzuf
stst yum version nogroups
stst yum install yourmom || true
stst yum install -y zzuf | tee /tmp/yum-release-testing-install-y-zzuf
stst cat /tmp/yum-release-testing-install-y-zzuf
stst yum version nogroups
stst yum remove -y zzuf | tee /tmp/yum-release-testing-remove-y-zzuf
stst cat /tmp/yum-release-testing-remove-y-zzuf
stst yum version nogroups

stst yum history list

stst yum localinstall || true
stst yum localinstall yourmom  || true

stst yum list updates
stst yum list obsoletes
stst yum list available
stst yum list installed
stst yum check-update || true

echo | stst yum update || true

stst yum groupinstall 'News Server'
stst yum groupremove 'News Server'
stst yum groupinstall -y 'News Server'
stst yum groupremove --setopt=clean_requirements_on_remove=true -y 'News Server'
# News server has a bunch of deps.
stst yum groupinstall -y 'News Server'

stst yum history undo last-4 -y

stst yum history list

utst yum grouplist
utst yum grouplist not_a_group
utst yum groupinfo || true
utst yum groupinfo not_a_group

stst yum info zzuf
utst yum info zzuf
stst yum makecache
utst yum makecache

stst yum clean all
utst yum clean all

stst yum -d0 -e0 install || true

utst yum --version

utst yum search || true

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

echo
echo
python -c 'print "*" * 79'
echo "Running 'make check', this should work but meh:"
python -c 'print "*" * 79'
make check
echo
echo

sleep 8

echo
echo
python -c 'print "=" * 79'
python -c 'print "*" * 79'
echo "Done, good to do a release. Running git2cl:"
make changelog || true
python -c 'print "*" * 79'
python -c 'print "=" * 79'
echo "
  Make sure you have edited yum/__init__.py:__version__ 
                            *.spec versions

  If not check --version again.

  ChangeLog has been updated, check with git diff, then:

git commit
git push

git tag -a yum-#-#-#
git push --tags

make archive

  Stick a build in rawhide.

  Update webpages:
    Main wiki page.
    /whatsnew
    /releases

  Upload tarball to yum.baseurl.org:/srv/projects/yum/web/download/x.y

  Send email to user and devel mailing list.
"
python -c 'print "=" * 79'
