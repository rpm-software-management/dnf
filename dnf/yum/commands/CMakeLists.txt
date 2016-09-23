FILE(GLOB commands_SRCS *.py)
INSTALL (FILES ${commands_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/yum/commands)
