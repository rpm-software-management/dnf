#!/usr/bin/python

# base class for boot loader updating code code for Update Agent
# Copyright (c) 2001 Red Hat, Inc.  Distributed under GPL.
#
# Author: Adrian Likins <alikins@redhat.com>


import os,sys
import iutil

class Error:
    # base class for client errors
    def __init__(self, errmsg):
        self.errmsg = errmsg

    def __repr__(self):
        #log.log_me(self.errmsg)
        return self.errmsg

def makeInitrd ( kernelTag, instRoot):
    initrd = "/boot/initrd-%s.img" % (kernelTag, )
    #log.log_me("Running \"/sbin/mkinitrd --ifneeded %s %s\" " %
    #           (initrd, kernelTag))
    exec_return = iutil.execWithRedirect("/sbin/mkinitrd",
                           [ "/sbin/mkinitrd",
                             "--ifneeded",
                             initrd,
                             kernelTag ],
                           stdout = None, stderr = None, searchPath = 1,
                           root = instRoot)

    # see if mkinitrd actually created a initrd, this seems to be
    # the only way to tell since it returns sucess if one isnt needed either
    if os.access(initrd, os.R_OK):
        initrdExists = 1
        #log.log_me("%s was created" % initrd)
    else:
        #log.log_me("No initrd was created by mkinitrd")
        initrdExists = None
    return (initrd,initrdExists)
