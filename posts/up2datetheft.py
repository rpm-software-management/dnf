import os
import sys

    
# these functions swiped from up2date.py, copyright Red Hat, Inc.
def install_lilo(kernelList):
    import lilocfg
    ret = lilocfg.installNewImages(kernelList,test=0)
    return ret


def install_grub(kernelList):
    import grubcfg
    ret  = grubcfg.installNewImages(kernelList,test=0)
    return ret


# mainly here to make conflicts resolution cleaner
def findDepLocal(ts, dep):
    header = None
    if dep[0] == '/':
        # Treat it as a file dependency
        try:
            hdr_arry = ts.dbMatch('basenames', dep)
        except:
            hdr_arry = []
            
        for h in hdr_arry:
            header = h
            break
    else:
        # Try it first as a package name
        try:
            hdr_arry = ts.dbMatch('name', 'dep')
        except:
            hdr_arry = []
        for h in hdr_arry:
            header = h
            break
        else:
            try:
                hdr_arry = ts.dbMatch('provides',dep)
            except:
                hdr_arry = []
            for h in hdr_arry:
                header = h
                break
            
    if header != None:
        return header
    else:
        return None
