SET (systemd_FILES
     dnf-automatic.service
     dnf-automatic.timer
     dnf-automatic-notifyonly.service
     dnf-automatic-notifyonly.timer
     dnf-automatic-install.service
     dnf-automatic-download.service
     dnf-automatic-download.timer
     dnf-automatic-install.service
     dnf-automatic-install.timer
     dnf-makecache.service
     dnf-makecache.timer)

INSTALL (FILES ${systemd_FILES} DESTINATION ${SYSTEMD_DIR})
