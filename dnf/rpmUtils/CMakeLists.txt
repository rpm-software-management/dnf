SET (rpmUtils_SRCS
    arch.py
    __init__.py
    miscutils.py
    oldUtils.py
    transaction.py
    updates.py)

INSTALL (FILES ${rpmUtils_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/rpmUtils)
