#!/bin/sh

# contribscript.sh -- run dnf from a local clone in a virtualenv

setup_const_py_in() {
    #prefix=$_WRD cd "$prefix"
    cp dnf/const.py.in dnf/const.py && \
        sed -i "s/^VERSION[[:blank:]]*=.*/VERSION='0.0.1-todo'/; s/^PLUGINPATH[[:blank:]]*=.*/PLUGINPATH='$pluginpath'/" dnf/const.py
}

setup_virtualenv_dnf() {
    dnfsrcdir="$VIRTUAL_ENV/src/dnf/dnf"

    pythonver="python3.12"
    systemsitepackages='/usr/lib64/python3.12/site-packages'
    VIRTUAL_ENV_sitepackages="${VIRTUAL_ENV}/lib/python3.12/site-packages"
    (set -x; cd "${VIRTUAL_ENV_sitepackages}";
        ln -s "${systemsitepackages}/rpm";
        ln -s "${systemsitepackages}/hawkey";
        ln -s "${systemsitepackages}/libcomps";
        ln -s "${dnfsrcdir}";
        #ln -s /usr/lib64/libdnf.so.2;
    )

}

test_virtualenv_dnf() {
    set -ex
    _WRD=$VIRTUAL_ENV/src/dnf
    #PYTHONPATH=${_WRD} LD_LIBRARY_PATH=/usr/lib64 python $_WRD/dnf/cli/main.py
    #PYTHONPATH=${_WRD} LD_LIBRARY_PATH=/usr/lib64 python $_WRD/dnf/cli/main.py
    #PYTHONPATH=${_WRD} LD_LIBRARY_PATH=/usr/lib64 python $_WRD/dnf/cli/main.py history -h
    #PYTHONPATH=${_WRD} python $_WRD/dnf/cli/main.py history -h
    python "${_WRD}/dnf/cli/main.py" history -h

    python "${_WRD}/dnf/cli/main.py" history store --all
    cat ./transactions.json

    python "${_WRD}/dnf/cli/main.py" history store --all --comments
    cat ./transactions.txt

    python "${_WRD}/dnf/cli/main.py" history store --all --commands
    cat ./transactions.txt

}

main() {
    if [ ! `id -g` -eq 0 ]; then
        (set -x; setup_virtualenv_dnf)
    fi
    test_virtualenv_dnf
}

main
