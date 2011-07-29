#!/bin/bash

# Only run if this flag is set. The flag is created by the yum-cron init
# script when the service is started -- this allows one to use chkconfig and
# the standard "service stop|start" commands to enable or disable yum-cron.
if [[ ! -f /var/lock/subsys/yum-cron ]]; then
  exit 0
fi

# Read configuration settings from the sysconfig directory.
if [[ -f /etc/sysconfig/yum-cron ]]; then
  source /etc/sysconfig/yum-cron
fi

# Only run on certain days of the week, based on the
# settings in the above-mentioned sysconfig file.
dow=`date +%w` 
DAYS_OF_WEEK=${DAYS_OF_WEEK:-0123456} 
if [[ "${DAYS_OF_WEEK/$dow/}" == "${DAYS_OF_WEEK}" ]]; then 
  exit 0 
fi 

# And only _clean_ on a subset of the configured days.
CLEANDAY=${CLEANDAY:-0}
if [[ "${CLEANDAY/$dow/}" == "${CLEANDAY}" ]]; then
  exit 0
fi

# Action!
exec /usr/sbin/yum-cron cleanup
