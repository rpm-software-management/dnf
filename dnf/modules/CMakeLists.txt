FILE(GLOB modules *.py)
INSTALL (FILES ${modules} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/modules)