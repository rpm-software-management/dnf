#!/usr/bin/python
#
# Module for munging lilo.conf lilo configurations file in the case
#   of installing new or updated kernel packages
#
# Copyright (c) 1999-2001 Red Hat, Inc.  Distributed under GPL.
#
# Authors: Matt Wilson <msw@redhat.com>
#          Adrian Likins <alikins@redhat.com>
#
"""Module for munging lilo.conf lilo configurations"""

import os,sys
import lilo, iutil
from i18n import _
import time
import string
from up2datetheft import findDepLocal
from rpmUtils import openrpmdb

# this tool is designed to setup lilo properly, including building a initrd,
# adding a new kernel to lilo.conf, testing lilo, and installing it
#
# first do sanity checks (or packages installed, is there space on /boot, etc)
#  then build the new lilo.conf, test it, install it
#
# then we parse in the existing one,figure out which kernel is the "default" one,
#  and then still all of it's arguments.
#

list_of_directives = ['label', 'root', 'append', 'video']
default_directives = ['read-only']
other_directives = ['initrd']
ignore_directives = ['alias']

global TEST
TEST=0

from bootloadercfg import Error, makeInitrd

class LiloConfError(Error):
    def __repr__(self):
        msg =  _("Error installing lilo.conf  The message was:\n") + self.errmsg
        #log.log_me(msg)
        return msg

class LiloConfRestoreError(Error):
    def __repr__(self):
        msg =  _("Error restoring the backup of lilo.conf  The backup was:\n") + self.errmsg
        #log.log_me(msg)
        return msg

class LiloInstallError(Error):
    def __repr__(self):
        msg =  _("Error installing the new bootloader: \n") + self.errmsg
        #log.log_me(msg)
        return msg

class LiloConfReadError(Error):
    def __repr__(self):
        msg = _("Error reading lilo.conf: The messages was:\n") + self.errmsg
        return msg


class LiloConfParseError(Error):
    def __repr__(self):
        msg = _("lilo options that are not supported by yum are used in the default lilo.conf. This file will not be modified. The options include:\n") + self.errmsg
        return msg



def addImage(newimage, initrd, label,config,default_image):
    path = "/boot/vmlinuz-%s" % newimage
    sl = lilo.LiloConfigFile(imageType = "image", path=path)
        
    for i in list_of_directives:
        tmp = default_image.getEntry(i)
        if tmp:
            sl.addEntry(i, tmp)

    entries = default_image.listEntries()
   
    # remove all the standard entries from entried
    # also remove stuff we dont want to copy, like 'alias'
    known_directives = default_directives+list_of_directives+other_directives+ignore_directives
    tmp_entries = {}
    for i in entries.keys():
        if i in known_directives:
            pass
        else:
            tmp_entries[i] = entries[i]
            
    # the ones we always add, ie "read-only"
    for i in default_directives:
        sl.addEntry(i)

    for i in tmp_entries.keys():
        sl.addEntry(i, tmp_entries[i])

    # FIXME (gen the initrd, first...)
    if initrd:
        sl.addEntry("initrd", initrd)

    if label:
        sl.addEntry("label", label)

    
            
    config.addImage(sl)


def installLiloConfig(config,backupfile):

    import shutil

    import stat
    liloperms = stat.S_IMODE(os.stat("/etc/lilo.conf")[stat.ST_MODE])
    try:
        shutil.copy("/etc/lilo.conf", backupfile)
        #log.log_me("making a backup copy of /etc/lilo.conf as %s" % backupfile)
    except:
        raise LiloConfError("unable to create a backup copy of lilo.conf")
    
    if TEST:
        config.write("/tmp/lilo.conf",perms = liloperms)
    else:
        try:
            config.write("/etc/lilo.conf",perms = liloperms)
            #log.log_me("writing out the new /etc/lilo.conf")
        except:
            raise LiloConfError("Unable to write out lilo.conf")

    return backupfile

def restoreLiloConfig(backupname):
    if TEST:
        return
    import shutil
    try:
        ret = shutil.copy(backupname, "/etc/lilo.conf")
        #log.log_me("restoring the backup file %s to /etc/lilo.conf" % backupname)
    except:
        raise LiloConfRestoreError(backupname)
    # dont really care to much if this fails
    os.remove(backupname)

def deleteLiloConfigBackup(backupfile):
    import shutil
    os.remove(backupfile)
    #log.log_me("Deleteing the backupfile %s" % backupfile)

def runLiloTest(instRoot):
    try:
        ret = iutil.execWithRedirect(instRoot + '/sbin/lilo' ,
                                   [ "lilo", "-t", "-r", instRoot ],
                                   stdout = None, stderr = None)
        #log.log_me("Running \" /sbin/lilo -t -r %s\"  (lilo test mode)" % instRoot)
    except RuntimeError, command:
        raise LiloInstallError("unable to run lilo. Not running as root?")
    except:
        raise LiloInstallError
    return ret

def runLilo(instRoot):
    if TEST:
        print """
        iutil.execWithRedirect(instRoot + '/sbin/lilo' ,
                               [ "lilo", "-r", instRoot ],
                               stdout = None)
                               """
        return 0
    else:
        try:
            ret = iutil.execWithRedirect(instRoot + '/sbin/lilo' ,
                                   [ "lilo", "-r", instRoot ],
                                   stdout = None)
            #log.log_me("Running \" /sbin/lilo -r %s \" " % instRoot)
        except RuntimeError, command:
            raise LiloInstallError("unable to run lilo. Not running as root?")
        except:
            raise LiloInstallError
    return ret


def backupName(labelName,imagelist):
    #this could be smarter
    backup = labelName+".bak"
    count = 1
    # see if it's going to be too long
    # leaving room for two digits of backups
    if len(backup) > 16:
        backup = labelName[:10]+".bak"

    # add a count to the bakup labels
    while (backup in imagelist):
        backup = backup+"%s" % count
        count = count + 1

    return backup


def findDefault(config,imagelist):
    defaultIsOther = None
    try:
        default = config.getEntry("default")
    except:
        # erk, bad
        default = None

    tmp_default = None
    
    if default:
        (imagetype, default_image,image_path,other) = config.getImage(default)
    else:
        # just to get me in the loop searching for the default image
        other = 1
        
    if other and default:
        defaultIsOther = 1
        
    
    if other:
        for image in imagelist:
            tmp_default = imagelist[0]
            (imagetype, default_image,image_path,other) = config.getImage(tmp_default)
        
    else:
        (imagetype, default_image,image_path,other) = config.getImage(default)

    if tmp_default:
        default = tmp_default
        
    return (default,imagetype, default_image,image_path,other,defaultIsOther)

# kluge for the new way of finding the default image
# not giving us anything meaningful for the label name
def genImageLabelType(imageType):
    # grrrr
    res = string.split(imageType, "kernel")
    if len(res[1]) == 0:
        tmp = "-up"
        return tmp

    tmp = res[1][:10]
    return tmp

def installNewImages(imageList,test=0,filename=None):
    # parse the existing config file
    config = lilo.LiloConfigFile()
    global TEST
    TEST=test

    label = "linux"

    if not filename:
        filename = "/etc/lilo.conf"
        
    # if there is no existing lilo.conf, I'm not smart enough to create one
    if not os.access(filename, os.R_OK):
        return None
    
    config.read(filename)
    if len(config.unsupported):
        raise LiloConfParseError("\n" + "%s" % config.unsupported)



    imagelist = config.listImages()
    # look at the default entry
    # assume it's valid and good, if not... uh, sorry, what else
    # can I do?
    (default, tmptype, default_image,image_path,other,defaultIsOther) = findDefault(config,imagelist)
    
    defaultType = None

    # open the rpmdb and look up the kernel path
    db = openrpmdb()
    header = findDepLocal(db,image_path)

    # this fails completely if the image_path is to
    # a file that cant be found in the rpmdb base. 
    # aka, it's not from an rpm currently isntalled
    if header:
        # the default is the name of the 
        defaultType = header["name"]
    else:
        # since the image is to a file that we know
        # nothing about but it's name, we cant do much.
        # we could try to guess based on the image name
        # if it's smp,enterprise,etc, but ick....
        defaultType = None
        
    rootDev = default_image.getEntry("root")

    # build the initrd, returns it's name and it's exit status
    for (newimage,imageType) in imageList:
        (initrd,initrdExists) = makeInitrd(newimage, "/")

        if imageType and imageType != defaultType:
            # linux-smp.linux-BOOT, etc
            label = "linux"+genImageLabelType(imageType)
        else:
            label = "linux"

        if TEST:
            print "newimage: %s" % newimage
            print "label: %s" % label
            print "defaultType: %s" % defaultType
            print "imageType: %s" % imageType
            print
            
        # initrd not needed
        if not initrdExists:
            initrd = None

        # if there exists an image with that name already, rename it
        if label in imagelist:
            (tmpType, old_image, tmp_path,other)  = config.getImage(label)
            new_old_label = backupName(label,imagelist)
            old_image.addEntry("label", new_old_label)
            #log.log_me("renaming the lilo.conf entry for %s to %s" %(label,new_old_label))
                       

        addImage(newimage, initrd, label, config, default_image)

        # uh huh..
        # figure out which kernel in the list matches the default
        # kernel type, and set that new kernel to the new default
        if defaultType:
            if imageType:
                if defaultType == imageType:
                    setdefault = 1
                else:
                    setdefault = 0
            else:
                setdefault = 0
        else:
            if imageType:
                setdefault = 0
            else:
                setdefault = 1

        if defaultIsOther:
            setdefault = None
        if setdefault:
            config.addEntry("default", label)
        
    # the default "backupname"
    backupfile = filename + ".yum-" + repr(time.time())
    # first, see if there are existing backup files
    # if so, choose-another
    while os.access(backupfile, os.F_OK):
        backupfile = backupfile + "_"

    #print config
    try:
        installLiloConfig(config,backupfile)
    except LiloConfError, info:
        restoreLiloConfig(backupfile)
        raise LiloConfError, info

    if TEST:
        print config
    # attempt a test run first just to be on the safe side
    try:
        ret = runLiloTest("/")
    except:
        #lilo failed for some reason
        ret = 1
    if ret and not TEST:
        restoreLiloConfig(backupfile)
        raise LiloConfError("test install of lilo failed")
        
    # runLilo will raise it's own err
    try:
        ret = runLilo("/")
    except:
        restoreLiloConfig(backupfile)
        raise LiloInstallError("unable to run lilo")

    # lilo ran, but existed with status 1
    if ret:
        restoreLiloConfig(backupfile)
        raise LiloInstallError("unable to restore the backup copy of lilo")
    else:
        #log.log_me("lilo updated succesfully")
        return 0
        



if __name__ == "__main__":

    import lilo
    import iutil
    import getopt
    import lilocfg

    filename = None
    arglist = sys.argv[1:]
    try:
        optlist, args = getopt.getopt(arglist,
                                      'a:d:',
                                      ['add=','del=',
                                       'file=','default'])
    except getopt.error, e:
        print(_("Error parsing command line arguments: %s")) % e
        sys.exit(1)

    addimage = 0
    delimage = 0
    print optlist
    for opt in optlist:
        if opt[0] == '-a' or opt[0] == '--add':
            addimage = 1
            newimage = opt[1]
        if opt[0] == '-d' or opt[0] == '--del':
            delimage = 1
        if opt[0] == '--file':
            filename = opt[1]

    kernel_list = [('2.4.2-0.1.49BOOT', "kernel-BOOT"),
                   ('2.4.2-0.1.49enterprise', "kernel-enterprise"),
                   ('2.4.2-0.1.49smp', "kernel-smp"),
                   ('2.4.2-0.1.49', "kernel")]

    kernel_list2 = [('2.4.2-0.1.49',"kernel"),
                   ('2.4.2-0.1.49enterprise', "kernel-enterprise"),
                   ('2.4.2-0.1.49smp', "kernel-smp"),
                   ('2.4.2-0.1.49BOOT', "kernel-BOOT")]
    
    kernel_list3 = [('2.4.2-0.1.49',"kernel")]

    kernel_list4 = [('2.4.2-0.1.49smp', "kernel-smp"),
                   ('2.4.2-0.1.49', "kernel")]

    kernel_list5 = [('2.4.7-2', "kernel"),
                    ('2.4.6-3.1BOOT', "kernel-BOOT")]
   
    kernel_list6 = [('2.4.9-13', "kernel"),
                    ('2.4.9-13smp', "kernel-smp")]


    print "filename: %s" % filename 
    print lilocfg.installNewImages(kernel_list6, filename=filename,test=1,)

    sys.exit()
