SET (systemd_FILES
     dnf-automatic.service
     dnf-automatic.timer
     dnf-makecache.service
     dnf-makecache.timer)

INSTALL (FILES ${systemd_FILES} DESTINATION ${SYSTEMD_DIR})
