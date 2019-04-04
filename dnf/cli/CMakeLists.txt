FILE(GLOB cli_SRCS *.py)
INSTALL (FILES ${cli_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/cli)
# completion_helper.py is generated so the glob alone won't see it:
INSTALL (FILES completion_helper.py DESTINATION ${PYTHON_INSTALL_DIR}/dnf/cli)

ADD_SUBDIRECTORY (commands)
