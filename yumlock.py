#!/usr/bin/python -t

#thanks to michael stenner for these straightforward lock and lock checking routines
import os

def lock(filename, contents='', mode=0777):
    try:
        fd = os.open(filename, os.O_EXCL|os.O_CREAT|os.O_WRONLY, mode)
    except OSError, msg:
        if not msg.strerror == "File exists": raise msg
        return 0
    else:
        os.write(fd, contents)
        os.close(fd)
        return 1

def unlock(filename):
    try:
        os.unlink(filename)
    except OSError, msg:
        pass
