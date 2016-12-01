#!/bin/bash
#run dnf
export GI_TYPELIB_PATH="/usr/local/lib64/girepository-1.0/"
export LD_LIBRARY_PATH="/usr/local/lib64/"
export PYTHONPATH="/home/test/dnf/"
/home/test/dnf/bin/dnf-2 "$@"
