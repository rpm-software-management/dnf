#!/bin/bash

# Only run if this flag file is set (by /etc/rc.d/init.d/yum-cron)
if [[ ! -f /var/lock/subsys/yum-cron ]]; then
  exit 0
fi

# Grab config settings
if [[ -f /etc/sysconfig/yum-cron ]]; then
  source /etc/sysconfig/yum-cron
fi

# Only run on certain days of the week 
dow=`date +%w` 
DAYS_OF_WEEK=${DAYS_OF_WEEK:-0123456} 
if [[ "${DAYS_OF_WEEK/$dow/}" == "${DAYS_OF_WEEK}" ]]; then 
  exit 0 
fi 

# And only _clean_ on a subset of that
CLEANDAY=${CLEANDAY:-0}
if [[ "${CLEANDAY/$dow/}" == "${CLEANDAY}" ]]; then
  exit 0
fi

# Action!
exec /usr/sbin/yum-cron cleanup
