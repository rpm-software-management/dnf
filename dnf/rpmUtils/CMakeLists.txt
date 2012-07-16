SET (rpmUtils_SRCS
    __init__.py
    arch.py
    error.py
    miscutils.py
    transaction.py)

INSTALL (FILES ${rpmUtils_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/rpmUtils)
