#!/bin/bash

LOCKDIR=/var/lock/yum-cron.lock
LOCKFILE=$LOCKDIR/pidfile
TSLOCK=$LOCKDIR/ts.lock
SCRIPTDIR=/usr/share/yum-cron/

if [ -z "$1" ]; then
  echo "Usage: yum-cron {update|cleanup|...}"
  exit 1
else
  ACTION=$1
fi

YUMSCRIPT=${SCRIPTDIR}/${ACTION}.yum
if [ ! -r $YUMSCRIPT ]; then
  echo "Script for action \"$ACTION\" is not readable in $SCRIPTDIR."
  exit 1
fi  

# Grab config settings
if [ -f /etc/sysconfig/yum-cron ]; then
  source /etc/sysconfig/yum-cron
fi
# set default for SYSTEMNAME
[ -z "$SYSTEMNAME" ]  && SYSTEMNAME=$( hostname ) 

# if DOWNLOAD_ONLY is set then we force CHECK_ONLY too.
# Gotta check before one can download!
if [ "$DOWNLOAD_ONLY" == "yes" ]; then
  CHECK_ONLY=yes
fi

YUMTMP=$(mktemp /var/run/yum-cron.XXXXXX)
touch $YUMTMP 
[ -x /sbin/restorecon ] && /sbin/restorecon $YUMTMP

# Note - the lockfile code doesn't try and use YUMTMP to email messages nicely.
# Too many ways to die, this gets handled by normal cron error mailing.
# Try mkdir for the lockfile, will test for and make it in one atomic action
if mkdir $LOCKDIR 2>/dev/null; then
  # store the current process ID in there so we can check for staleness later
  echo "$$" >"${LOCKFILE}"
  # and clean up locks and tempfile if the script exits or is killed  
  trap "{ rm -f $LOCKFILE $TSLOCK; rmdir $LOCKDIR 2>/dev/null; rm -f $YUMTMP; exit 255; }" INT TERM EXIT
else
  # lock failed, check if process exists.  First, if there's no PID file
  # in the lock directory, something bad has happened, we can't know the
  # process name, so clean up the old lockdir and restart
  if [ ! -f $LOCKFILE ]; then
    rmdir $LOCKDIR 2>/dev/null
    echo "yum-cron: no lock PID, clearing and restarting myself" >&2
    exec $0 "$@"
  fi
  OTHERPID="$(cat "${LOCKFILE}")"
  # if cat wasn't able to read the file anymore, another instance probably is
  # about to remove the lock -- exit, we're *still* locked
    if [ $? != 0 ]; then
      echo "yum-cron: lock failed, PID ${OTHERPID} is active" >&2
      exit 0
    fi
    if ! kill -0 $OTHERPID &>/dev/null; then
      # lock is stale, remove it and restart
      echo "yum-cron: removing stale lock of nonexistant PID ${OTHERPID}" >&2
      rm -rf "${LOCKDIR}"
      echo "yum-cron: restarting myself" >&2
      exec $0 "$@"
    else
      # Remove stale (more than a day old) lockfiles
      find $LOCKDIR -type f -name 'pidfile' -amin +1440 -exec rm -rf $LOCKDIR \;
      # if it's still there, it wasn't too old, bail
      if [ -f $LOCKFILE ]; then
        # lock is valid and OTHERPID is active - exit, we're locked!
        echo "yum-cron: lock failed, PID ${OTHERPID} is active" >&2
        exit 0
      else
        # lock was invalid, restart
        echo "yum-cron: removing stale lock belonging to stale PID ${OTHERPID}" >&2
        echo "yum-cron: restarting myself" >&2
        exec $0 "$@"
      fi
    fi
fi

# Now, do the actual work; we special case "update" because it has
# complicated conditionals; for everything else we just run yum with the
# right parameters and corresponding script.  Right now, that's just
# "cleanup" but theoretically there could be other actions.

{
  case "$ACTION" in
    update)
        if [ "$CHECK_ONLY" == "yes" ]; then
          touch $TSLOCK
          /usr/bin/yum $YUM_PARAMETER -e 0 -d 0 -y check-update 1> /dev/null 2>&1
          case $? in
            1)   exit 1;;
            100) echo "New updates available for host $SYSTEMNAME";
                 /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y -C check-update
                 if [ "$DOWNLOAD_ONLY" == "yes" ]; then
                     /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y --downloadonly update
                     echo "Updates downloaded. Use \"yum -C update\" manually to install them."
                 fi
                 ;;
          esac
        elif [ "$CHECK_FIRST" == "yes" ]; then
          # Don't run if we can't access the repos
          touch $TSLOCK
          /usr/bin/yum $YUM_PARAMETER -e 0 -d 0 check-update 2>&-
          case $? in
            1)   exit 1;;
            100) /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y update yum
                 /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
                 ;;
          esac
        else
          touch $TSLOCK
          /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y update yum
          /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
        fi
        ;;
    *)
        /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
        ;;
  esac       

} >> $YUMTMP 2>&1

if [ ! -z "$MAILTO" ] && [ -x /bin/mail ]; then 
# if MAILTO is set, use mail command (ie better than standard mail with cron output) 
  [ -s "$YUMTMP" ] && mail -s "System update: $SYSTEMNAME" $MAILTO < $YUMTMP 
else 
# default behavior is to use cron's internal mailing of output from cron-script
  cat $YUMTMP
fi 
rm -f $YUMTMP 

exit 0
