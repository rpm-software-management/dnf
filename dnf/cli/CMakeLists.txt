SET(cli_SRCS
    callback.py
    cli.py
    output.py
    shell.py
    utils.py
    yumcommands.py
    yummain.py)
INSTALL (FILES ${cli_SRCS} DESTINATION ${PYTHON_INSTALL_DIR}/dnf/cli)
