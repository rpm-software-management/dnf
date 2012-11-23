SET (systemd_FILES
     dnf-makecache.service
     dnf-makecache.timer)

INSTALL (FILES ${systemd_FILES} DESTINATION ${SYSTEMD_DIR})
