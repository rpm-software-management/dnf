FILE(GLOB module *.py)
INSTALL (FILES ${module} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/module)
