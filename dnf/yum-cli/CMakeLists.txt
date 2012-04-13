SET(yum-cli_SRCS
    callback.py
    cli.py
    output.py
    shell.py
    utils.py
    yumcommands.py
    yummain.py)
INSTALL (FILES ${yum-cli_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/yum-cli)
