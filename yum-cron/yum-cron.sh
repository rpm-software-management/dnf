#!/bin/bash

# This script is designed to be run from cron to automatically keep your
# system up to date with the latest security patches and bug fixes. It
# can download and/or apply package updates as configured in
# /etc/sysconfig/yum-cron.


# This is used by /etc/init.d/yum-cron on shutdown to protect against
# abruptly shutting down mid-transaction. Therefore, you shouldn't change
# it without changing that.
PIDFILE=/var/lock/yum-cron.pid


# This is the home of the yum scripts which power the various actions the
# yum-cron system performs.
SCRIPTDIR=/usr/share/yum-cron/

# If no command line options were given, exit with a usage message.
if [[ -z "$1" ]]; then
  echo "Usage: yum-cron {update|cleanup|...}"
  exit 1
else
  ACTION=$1
fi

# If a command line option was given, it must match a yum script.
YUMSCRIPT=${SCRIPTDIR}/${ACTION}.yum
if [[ ! -r $YUMSCRIPT ]]; then
  echo "Script for action \"$ACTION\" is not readable in $SCRIPTDIR."
  exit 1
fi  

# Read the settings from our config file.
if [[ -f /etc/sysconfig/yum-cron ]]; then
  source /etc/sysconfig/yum-cron
fi

# If no system name is set, use the hostname.
[[ -z "$SYSTEMNAME" ]] && SYSTEMNAME=$( hostname ) 

# If DOWNLOAD_ONLY is set, then we force CHECK_ONLY too.
# Gotta check for updates before we can possibly download them.
[[ "$DOWNLOAD_ONLY" == "yes" ]] && CHECK_ONLY=yes

# This holds the output from the "meat" of this script, so that it can
# be nicely mailed to the configured destination when we're done.
YUMTMP=$(mktemp /var/run/yum-cron.XXXXXX)
touch $YUMTMP 
[[ -x /sbin/restorecon ]] && /sbin/restorecon $YUMTMP

# Here is the gigantic block of lockfile logic.
#
# Note: the lockfile code doesn't currently try and use YUMTMP to email
# messages nicely, so this gets handled by normal cron error mailing.
#
	
# We use noclobber for the pidfile, as this will test for and if possible 
# create the file in one atomic action. (So there's no race condition.) The 
# current process ID is stored in the file so we can check for staleness 
# later.
if (set -o noclobber; echo "$$" > $PIDFILE) 2>/dev/null; then
  # We got the lock. So now, set a trap to clean up locks and the output
  # tempfile when the script exits or is killed.
  trap "rm -f $PIDFILE" INT TERM EXIT
else
  # Lock failed -- check if a running process exists.  
  # First, if there's no PID file in the lock directory, something bad has
  # happened.  We can't know the process name, so, restart.
  if [[ ! -f $PIDFILE ]]; then
    echo "yum-cron: no lock PID, restarting myself" >&2
    exec $0 "$@"
  fi
  OTHERPID="$(< $PIDFILE)" 2>/dev/null
  # if cat wasn't able to read the file anymore, another instance probably is
  # about to remove the lock -- exit, we're *still* locked
  if [[ $? != 0 ]]; then
    echo "yum-cron: lock failed, PID ${OTHERPID} is active" >&2
    exit 0
  fi
  if ! kill -0 $OTHERPID &>/dev/null; then
    # Lock is stale. Remove it and restart.
    echo "yum-cron: removing stale lock of nonexistant PID ${OTHERPID}" >&2
    rm -f $PIDFILE
    echo "yum-cron: restarting myself" >&2
    exec $0 "$@"
  else
    # Remove lockfiles more than a day old -- they must be stale.
    find $PIDFILE -type f -name 'yum-cron.pid' -amin +1440 -exec rm -f $PIDFILE \;
    # If it's still there, it *wasn't* too old. Bail!
    if [[ -f $PIDFILE ]]; then
      # Lock is valid and OTHERPID is active -- exit, we're locked!
      echo "yum-cron: lock failed, PID ${OTHERPID} is active" >&2
      exit 0
    else
      # Lock was invalid. Restart.
      echo "yum-cron: removing stale lock belonging to stale PID ${OTHERPID}" >&2
      rm -f $PIDFILE
      echo "yum-cron: restarting myself" >&2
      exec $0 "$@"
    fi
  fi
fi

# Now, do the actual work.

# We special case "update" because it has complicated conditionals; for
# everything else we just run yum with the right parameters and
# corresponding script.  Right now, that's just "cleanup" but theoretically
# there could be other actions.
{
  case "$ACTION" in
    update)
        # There's three broad possibilties here:
        #   CHECK_ONLY (possibly with DOWNLOAD_ONLY)
        #   CHECK_FIRST (exits _silently_ if we can't access the repos)
        #   nothing special -- just do it
        # Note that in all cases, yum is updated first, and then 
        # everything else.
        if [[ "$CHECK_ONLY" == "yes" ]]; then
          /usr/bin/yum $YUM_PARAMETER -e 0 -d 0 -y check-update 1> /dev/null 2>&1
          case $? in
            1)   exit 1;;
            100) echo "New updates available for host $SYSTEMNAME";
                 /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y -C check-update
                 if [[ "$DOWNLOAD_ONLY" == "yes" ]]; then
                     /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y --downloadonly update
                     echo "Updates downloaded. Use \"yum -C update\" manually to install them."
                 fi
                 ;;
          esac
        elif [[ "$CHECK_FIRST" == "yes" ]]; then
          # Don't run if we can't access the repos -- if this is set, 
          # and there's a problem, we exit silently (but return an error
          # code).
          /usr/bin/yum $YUM_PARAMETER -e 0 -d 0 check-update 2>&-
          case $? in
            1)   exit 1;;
            100) /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y update yum
                 /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
                 ;;
          esac
        else
          # and here's the "just do it".
          /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y update yum
          /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
        fi
        ;;
    *)
        /usr/bin/yum $YUM_PARAMETER -e ${ERROR_LEVEL:-0} -d ${DEBUG_LEVEL:-0} -y shell $YUMSCRIPT
        ;;
  esac       

} >> $YUMTMP 2>&1

if [[ ! -z "$MAILTO" && -x /bin/mail ]]; then 
# If MAILTO is set, use mail command for prettier output.
  [[ -s "$YUMTMP" ]] && \
    mail -s "System update: $SYSTEMNAME" $MAILTO < $YUMTMP && \
    rm -f $YUMTMP
else 
# The default behavior is to use cron's internal mailing of output.
  cat $YUMTMP && rm -f $YUMTMP
fi 

exit 0
