#!/usr/bin/python
#
# Check to see whether it looks like GRUB or LILO is the boot loader
# being used on the system.
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os,sys
import string
from i18n import _


grubConfigFile = "/boot/grub/grub.conf"
liloConfigFile = "/etc/lilo.conf"


# XXX: this is cut and pasted directly from booty/bootloaderInfo.py
# should eventually just go from there
def getDiskPart(dev):
    """Return (disk, partition number) tuple for dev"""
    cut = len(dev)
    if (dev[:3] == "rd/" or dev[:4] == "ida/" or
        dev[:6] == "cciss/"):
        if dev[-2] == 'p':
            cut = -1
        elif dev[-3] == 'p':
            cut = -2
    else:
        if dev[-2] in string.digits:
            cut = -2
        elif dev[-1] in string.digits:
            cut = -1

    name = dev[:cut]
    
    # hack off the trailing 'p' from /dev/cciss/*, for example
    if name[-1] == 'p':
        for letter in name:
            if letter not in string.letters and letter != "/":
                name = name[:-1]
                break

    if cut < 0:
        partNum = int(dev[cut:]) - 1
    else:
        partNum = None

    return (name, partNum)


def getRaidDisks(raidDevice):
    rc = []

    try:
        f = open("/proc/mdstat", "r")
        lines = f.readlines()
        f.close()
    except:
        return rc
    
    for line in lines:
        fields = string.split(line, ' ')
        if fields[0] == raidDevice:
            for field in fields[4:]:
                if string.find(field, "[") == -1:
                    continue
                dev = string.split(field, '[')[0]
                if len(dev) == 0:
                    continue
                disk = getDiskPart(dev)[0]
                rc.append(disk)

    return rc
            

def getBootBlock(bootDev):
    """Get the boot block from bootDev.  Return a 512 byte string."""
    block = " " * 512
    if bootDev is None:
        return block

    # get the devices in the raid device
    if bootDev[5:7] == "md":
        bootDevs = getRaidDisks(bootDev[5:])
        bootDevs.sort()
    else:
        bootDevs = [ bootDev[5:] ]

    # FIXME: this is kind of a hack
    # look at all of the devs in the raid device until we can read the
    # boot block for one of them.  should do this better at some point
    # by looking at all of the drives properly
    for dev in bootDevs:
        try:
#            print "checking %s\n" %(dev,)
            fd = os.open("/dev/%s" % (dev,), os.O_RDONLY)
            block = os.read(fd, 512)
            os.close(fd)
            return block
        except:
            pass
    return block

# takes a line like #boot=/dev/hda and returns /dev/hda
# also handles cases like quoted versions and other nonsense
def getBootDevString(line):
    dev = string.split(line, '=')[1]
    dev = string.strip(dev)
    dev = string.replace(dev, '"', '')
    dev = string.replace(dev, "'", "")
    return dev

def whichBootLoader(instRoot = "/"):
    haveGrubConf = 1
    haveLiloConf = 1
    
    bootDev = None
    
    # make sure they have the config file, otherwise we definitely can't
    # use that bootloader
    if not os.access(instRoot + grubConfigFile, os.R_OK):
        haveGrubConf = 0
    if not os.access(instRoot + liloConfigFile, os.R_OK):
        haveLiloConf = 0

    if haveGrubConf:
        f = open(grubConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:6] == "#boot=":
                bootDev = getBootDevString(line)
                break

        block = getBootBlock(bootDev)
        # XXX I don't like this, but it's what the maintainer suggested :(
        if string.find(block, "GRUB") >= 0:
            return "GRUB"

    if haveLiloConf:
        f = open(liloConfigFile, "r")
        lines = f.readlines()
        for line in lines:
            if line[0:5] == "boot=":
                bootDev = getBootDevString(line)                
                break

        block = getBootBlock(bootDev)
        # this at least is well-defined
        if block[6:10] == "LILO":
            return "LILO"


if __name__ == "__main__":
    bootloader = whichBootLoader()
    if bootloader:
        print _("Found %s.") % (bootloader)
    else:
        print _("Unable to determine boot loader.")
