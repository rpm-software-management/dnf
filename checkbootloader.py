#!/usr/bin/python
#
# Check to see whether it looks like GRUB or LILO is the boot loader
# being used on the system.
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os,sys
import string

grubConfigFile = "/boot/grub/grub.conf"
liloConfigFile = "/etc/lilo.conf"


def whichBootLoader():
    haveGrubConf = 1
    haveLiloConf = 1
    
    bootDev = None
    
    # make sure they have the config file, otherwise we definitely can't
    # use that bootloader
    if not os.access(grubConfigFile, os.R_OK):
        haveGrubConf = 0
    if not os.access(liloConfigFile, os.R_OK):
        haveLiloConf = 0

    if haveGrubConf:
        f = open(grubConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:6] == "#boot=":
                bootDev = line[6:-1]
                break

        fd = os.open(bootDev, os.O_RDONLY)
        block = os.read(fd, 512)
        os.close(fd)

        # XXX I don't like this, but it's what the GRUB maintainer suggested
        if string.find(block, "GRUB") >= 0:
            return "GRUB"

    if haveLiloConf:
        f = open(liloConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:5] == "boot=":
                bootDev = line[5:-1]
                break

        fd = os.open(bootDev, os.O_RDONLY)
        block = os.read(fd, 512)
        os.close(fd)

        # this at least is well-defined
        if block[6:10] == "LILO":
            return "LILO"


if __name__ == "__main__":
    bootloader = whichBootLoader()
    if bootloader:
        print "Found %s." % (bootloader)
    else:
        print "Unable to determine boot loader."
