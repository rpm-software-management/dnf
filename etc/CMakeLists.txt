INSTALL (PROGRAMS "dnf-makecache.cron" DESTINATION ${SYSCONFDIR}/cron.hourly)
INSTALL (FILES "collect_dnf.conf" DESTINATION ${SYSCONFDIR}/libreport/events.d/)
ADD_SUBDIRECTORY (dnf)
