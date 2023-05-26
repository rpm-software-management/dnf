INSTALL (FILES "dnf-strict.conf" "dnf.conf" "automatic.conf" DESTINATION ${SYSCONFDIR}/dnf)
ADD_SUBDIRECTORY (aliases.d)
ADD_SUBDIRECTORY (protected.d)
