#!/usr/bin/python
#
# Module for munging lilo.conf lilo configurations file in the case
#   of installing new or updated kernel packages
#
# Copyright (c) 1999-2001 Red Hat, Inc.  Distributed under GPL.
#
# Authors: Adrian Likins <alikins@redhat.com>
#

import os,sys
import iutil
from i18n import _
import time
import string
from up2datetheft import findDepLocal
from rpmUtils import openrpmdb
from bootloadercfg import Error, makeInitrd

class GrubbyRuntimeError(Error):
    def __repr__(self):
        msg = _("Unable to run grubby correctly: the message was:\n") + self.errmsg
        return msg

# fire off grubby to find the default
def findDefault():
    try:
        pipe = os.popen("/sbin/grubby --default-kernel")
        ret = pipe.read()
        ret = string.strip(ret)
        
       # log.log_me("""Running /sbin/grubby --default-kernel""")
    except RuntimeError, command:
        raise GrubbyRuntimeError("unable to run grubby. Not running as root?")
    
    return ret

def setDefault(newImage):
    try:
        ret = iutil.execWithRedirect("/sbin/grubby", ["grubby", "--set-default", "/boot/vmlinuz-%s" % newImage])
    except RuntimeError, command:
        raise GrubbyRuntimeError("unable to run grubby. Not running as root?")

    # FIXME
    # add error checking here? grubby seems to always return 0
    return ret
    
    
def installNewImages(imageList, test=0, filename=None):

    # find out what image is 
    defaultImagePath = findDefault()
    defaultType = None
    
    # open the rpmdb and look up the kernel path
    db = openrpmdb()
    if defaultImagePath != "":
        header = findDepLocal(db,defaultImagePath)
    else:
        header = None
        
    if header:
        # the default is the name of the 
        defaultType = header["name"]
    else:
        defaultType = None

    
    # look for a kernel image matching the default in the list of
    # kernels I'm installing...
    # if we dont match anything, dont set linux to the default of any sort
    for (newimage, imageType) in imageList:
        if defaultType == imageType:
            setDefault(newimage)

    # not much testing we can do here... ;-<
    return 0        
