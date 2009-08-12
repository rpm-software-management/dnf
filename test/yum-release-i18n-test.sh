#!/bin/bash -e

#######################################################
### Settings ##########################################
#######################################################

# Change to true, to not perform the "root" commands
SUDO_CMD=sudo

# Do we want full info/list output (takes a while, and outputs a _lot_)
FULL_PKG_OUTPUT=false

#  Do we want to play with the livna repo. includes install/remove
LIVNA=true

# Pkg to add/remove/etc. from livna
PKG_LIVNA=amule

# Pkg that doesn't exist
PKG_BAD=pkg-no-exist-kthx-bai-OMGWTFBBQ

#  Run tests the "fail", like installing packages for which we don't have the
# key. If you run these you need to look to see what the output is.
# FIXME: need a more automated way to see if we are getting Unicode*Error
RUN_FAILURES=true

_yes=''
if [ "x$1" = "x-y" ]; then
  _yes='-y'
fi

beg_hdr="
==============================================================================="
end_hdr="\
-------------------------------------------------------------------------------
"

I18N="C \
 da_DA da_DA.UTF-8 \
 de_DE de_DE.UTF-8 \
 fr_FR fr_FR.UTF-8 \
 it_IT it_IT.UTF-8 \
 ms_MS ms_MS.UTF-8 \
 nb_NB nb_NB.UTF-8 \
 pl_PL pl_PL.UTF-8 \
 pt_PT pt_PT.UTF-8 \
 pt_BR pt_BR.UTF-8 \
 ru_RU ru_RU.UTF-8 \
 sr_SR sr_SR.UTF-8 sr_SR@latin sr_SR@latin.UTF-8 \
 en_US en_US.UTF-8 \
 BAD_LOCALE"

cmd()
{
  echo $beg_hdr
  echo "Doing: LANG=$lang yum --enablerepo=rawhide $@"
  echo $end_hdr
  LANG=$lang yum --enablerepo=rawhide "$@"
}
scmd()
{
  echo $beg_hdr
  echo "Doing: LANG=$lang $SUDO_CMD yum $@"
  echo $end_hdr
  LANG=$lang $SUDO_CMD yum "$@"
}
lcmd()
{
  $LIVNA && echo $beg_hdr
  $LIVNA && echo "Doing: LANG=$lang yum --enablerepo=livna $@"
  $LIVNA && echo $end_hdr
  $LIVNA && LANG=$lang yum --enablerepo=livna "$@"
}
lscmd()
{
  $LIVNA && echo $beg_hdr
  $LIVNA && echo "Doing: LANG=$lang $SUDO_CMD yum --enablerepo=livna $@"
  $LIVNA && echo $end_hdr
  $LIVNA && LANG=$lang $SUDO_CMD yum --enablerepo=livna "$@"
}

tst()
{
  # Using ¶ because it doesn't match anything
  cmd search fedora linux ® $PKG_BAD ¶
  cmd search fedora linux ® $PKG_BAD ¶ | cat

  cmd list afflib libselinux linux $PKG_BAD ¶
  cmd list afflib libselinux linux $PKG_BAD ¶ | cat
  cmd info afflib libselinux linux $PKG_BAD ¶
  cmd info afflib libselinux linux $PKG_BAD ¶ | cat

  cmd grouplist
  cmd grouplist | cat
  # Games and Entertainment joy
  lcmd grouplist
  lcmd grouplist | cat

  cmd groupinfo 'Games and Entertainment'
  cmd groupinfo 'Games and Entertainment' | cat
  cmd groupinfo 'ଖେଳ ଏବଂ ମନୋରଞ୍ଜନ'
  cmd groupinfo 'ଖେଳ ଏବଂ ମନୋରଞ୍ଜନ' | cat
  # Games and Entertainment joy
  lcmd groupinfo 'Games and Entertainment'
  lcmd groupinfo 'Games and Entertainment' | cat
  lcmd groupinfo 'ଖେଳ ଏବଂ ମନୋରଞ୍ଜନ'
  lcmd groupinfo 'ଖେଳ ଏବଂ ମନୋରଞ୍ଜନ' | cat

  $FULL_PKG_OUTPUT && cmd list
  $FULL_PKG_OUTPUT && cmd list | cat
  $FULL_PKG_OUTPUT && cmd info
  $FULL_PKG_OUTPUT && cmd info | cat
 
  #  This always fails, so we need to "look" if it does so with an encoding
  # problem or the real one
  ($RUN_FAILURES && cmd help) || true
  $RUN_FAILURES && sleep 3
  #  This always fails, so we need to "look" if it does so with an encoding
  # problem or the real one
  ($RUN_FAILURES && (cmd help | cat)) || true
  $RUN_FAILURES && sleep 3
  for i in install remove check-update update list info provides; do
    cmd help $i
    cmd help $i | cat
  done
  cmd --help
  cmd --help | cat
  #  This always fails, so we need to "look" if it does so with an encoding
  # problem or the real one
  ($RUN_FAILURES && cmd) || true
  $RUN_FAILURES && sleep 3
  #  This always fails, so we need to "look" if it does so with an encoding
  # problem or the real one
  ($RUN_FAILURES && (cmd | cat)) || true
  $RUN_FAILURES && sleep 3

  scmd install bash
  scmd install $PKG_BAD
  scmd remove  $PKG_BAD

  # Test livna, missing keys and install/remove
  $LIVNA && $SUDO_CMD mv /etc/pki/rpm-gpg/RPM-GPG-KEY-livna .
  ($LIVNA && $SUDO_CMD rpm -e gpg-pubkey-a109b1ec-3f6e28d5) || true
  #  This always fails, so we need to "look" if it does so with an encoding
  # problem or the real one
  ($RUN_FAILURES && lscmd install $_yes $PKG_LIVNA) || true
  $RUN_FAILURES && $LIVNA && sleep 1
  $LIVNA && $SUDO_CMD mv RPM-GPG-KEY-livna /etc/pki/rpm-gpg/
  lscmd install -y $PKG_LIVNA
  lscmd remove  -y $PKG_LIVNA
}


for lang in $I18N; do
 tst
done
