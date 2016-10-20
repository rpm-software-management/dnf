INSTALL (FILES "dnf.conf" "automatic.conf" "automatic-install.conf" DESTINATION ${SYSCONFDIR}/dnf)
ADD_SUBDIRECTORY (protected.d)
