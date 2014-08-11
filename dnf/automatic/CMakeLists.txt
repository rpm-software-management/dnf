FILE(GLOB automatic_SRCS *.py)
INSTALL (FILES ${automatic_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/automatic)
