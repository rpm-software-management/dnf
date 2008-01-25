#!/bin/bash

#######################################################
### Settings ##########################################
#######################################################

USE_LOCAL_YUM_CONF=0

FIXWORKDIR=/tmp/yum-release-test

#WORKDIR=$FIXWORKDIR  # always run on same directory 
                     #  and don't do expensive tests
WORKDIR=`mktemp -d` # always start from scratch
                    #  and do full tests

# path to executables
YUMBINARY=/home/ffesti/CVS/yum/yummain.py
YUMBINARY=yum
YUMDOWNLOADER=(yumdownloader -d 0 --disablerepo=updates)
YUMDOWNLOADERUPDATES=(yumdownloader -d 0 --enablerepo=updates)

# for testing fedora releases
YUM=($YUMBINARY -d 0 --installroot=$WORKDIR --disablerepo=updates )
YUMUPDATES=($YUMBINARY -d 0 --installroot=$WORKDIR --enablerepo=updates )

# for fedora devel
# XXX TODO

RPM=(rpm --root $WORKDIR)

# Adjust size of base install
#DEFAULTGROUPS=("Office/Productivity" "GNOME Desktop Environment" "Games and Entertainment" "Sound and Video" "Graphical Internet" "System Tools" Core Base Editors "X Window System" )
DEFAULTGROUPS=(Base Core)



#######################################################
### end of settings ###################################
#######################################################

if [ `whoami` != root ] ; then
  echo You must be root to run this script
  exit 1
fi

mkdir -p $WORKDIR/var/cache/yum
mkdir -p $WORKDIR/var/lib/yum
mkdir -p $WORKDIR/var/log
mkdir -p $WORKDIR/tmp
mkdir -p $WORKDIR/etc/yum.repos.d


if [ "$USE_LOCAL_YUM_CONF" == 1 ] ; then
  # copy repos into build root to take advance of local mirrors
  echo "Using local yum repos"
  cp /etc/yum.repos.d/*.repo $WORKDIR/etc/yum.repos.d/
else
  echo "Not using local yum repos"
  yumdownloader --destdir $WORKDIR/tmp fedora-release
  rpm -i --nodeps --root $WORKDIR $WORKDIR/tmp/fedora-release\*.noarch.rpm
  rm -f $WORKDIR/tmp/fedora-release\*.noarch.rpm
fi

echo "Using $WORKDIR"


if [ ! -d $WORKDIR/usr/bin ]; then
  echo
  echo "yum groupinstall ${DEFAULTGROUPS[@]}"
  "${YUM[@]}" -y groupinstall "${DEFAULTGROUPS[@]}"
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
  echo "Check for vim-minimal"
  "${RPM[@]}" -q vim-minimal > /dev/null
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
else
  echo Ommiting base install
fi

#"${YUMUPDATES[@]}" list updates
#rm -rf $WORKDIR
#exit 0

echo
echo "yum remove vim-minimal"
"${YUM[@]}" -y remove vim-minimal
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
echo "Check if vim-minimal is removed"
"${RPM[@]}" -q vim-minimal > /dev/null
if [ "X$?" == "X1" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum install vim-minimal | cat"
"${YUM[@]}" -y install vim-minimal | cat
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
echo "Check vim-minimal"
"${RPM[@]}" -q vim-minimal > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum install bash (already installed)"
"${YUM[@]}" install bash
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum install fOObAr (not available)"
"${YUM[@]}" install fOObAr
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

if [ $WORKDIR != $FIXWORKDIR ] ; then

  echo
  echo "yum groupinstall Graphics"
  "${YUM[@]}" -y groupinstall Graphics
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
  echo "Check gimp"
  "${RPM[@]}" -q gimp > /dev/null
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

  echo
  echo "yum groupremove Graphics"
  "${YUM[@]}" -y groupremove Graphics
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
  echo "Check if gimp is removed"
  "${RPM[@]}" -q gimp > /dev/null
  if [ "X$?" == "X1" ] ; then echo " OK"; else echo " FAILED"; fi

  echo
  echo "yum clean all"
  "${YUM[@]}" clean all
  if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

fi 

echo
echo "yum makecache"
"${YUM[@]}" makecache
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo yumdownloader emacs
"${YUMDOWNLOADER[@]}" --destdir $WORKDIR/tmp --resolve emacs
"${YUMDOWNLOADER[@]}" --destdir $WORKDIR/tmp --resolve emacs-common
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
echo yum localinstall emacs\*.rpm
"${YUM[@]}" localinstall -y $WORKDIR/tmp/*.rpm
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
echo "Check emacs"
"${RPM[@]}" -q emacs > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

rm -f $WORKDIR/tmp/*.rpm

echo
echo yumdownloader emacs
"${YUMDOWNLOADERUPDATES[@]}" --destdir $WORKDIR/tmp --resolve emacs
"${YUMDOWNLOADERUPDATES[@]}" --destdir $WORKDIR/tmp --resolve emacs-common
echo yum localupdate emacs\*.rpm
"${YUM[@]}" localupdate -y $WORKDIR/tmp/emacs*.rpm
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum check-update # false"
"${YUM[@]}" check-update
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi
echo "yum check-update # true"
"${YUMUPDATES[@]}" check-update > /dev/null
if [ "X$?" == "X100" ] ; then echo " OK"; else echo " FAILED or uptodate"; fi

echo
echo yum update glibc
GLIBC=`"${RPM[@]}" -q glibc`
"${YUMUPDATES[@]}" -y update glibc
UGLIBC=`"${RPM[@]}" -q glibc`
if [ "$GLIBC" != "$UGLIBC" ] ; then 
  echo " OK"; 
else 
  echo " FAILED or uptodate"; 
fi

echo 
echo yum update
KERNEL=`"${RPM[@]}" -q kernel`
"${YUMUPDATES[@]}" -y update
UKERNEL=`"${RPM[@]}" -q kernel` 
if [ "$KERNEL" != "$UKERNEL" ] ; then 
  echo " OK"; 
else 
  echo " FAILED or uptodate"; 
fi

echo
echo "yum --version"
"${YUM[@]}" --version
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

#"${YUM[@]}" shell
#   repo
#   config
#   etc  

echo
echo "yum search kernel"
"${YUM[@]}" search kernel > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum provides kernel"
"${YUM[@]}" provides kernel > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum info kernel"
"${YUM[@]}" info kernel > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum groupinfo Core"
"${YUM[@]}" groupinfo Core > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum deplist bash"
"${YUM[@]}" deplist bash > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum grouplist"
"${YUM[@]}" grouplist > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum list updates"
"${YUM[@]}" list updates > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum list obsoletes"
"${YUM[@]}" list obsoletes > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum list available"
"${YUM[@]}" list available > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

echo
echo "yum list installed"
"${YUM[@]}" list installed > /dev/null
if [ "X$?" == "X0" ] ; then echo " OK"; else echo " FAILED"; fi

if [ $WORKDIR != $FIXWORKDIR ] ; then
  echo Deleting $WORKDIR
  rm -rf $WORKDIR
fi
