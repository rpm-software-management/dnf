#!/usr/bin/python -tt

import rpm
import types
import os
import gzip
import sys
from gzip import write32u, FNAME
from urlgrabber.grabber import URLGrabError
from zlib import error as zlibError

def log(num, msg):
    print >>sys.stderr, msg
errorlog = log

def _(msg):
    return msg
    

# pylint: disable-msg=E0602

def checkheader(headerfile, name, arch):
    """check a header by opening it and comparing the results to the name and arch
       we believe it to be for. if it fails raise URLGrabError(-1)"""
    h = Header_Work(headerfile)
    fail = 0
    if h.hdr is None:
        fail = 1
    else:
        if name != h.name() or arch != h.arch():
            fail = 1
    if fail:
        raise URLGrabError(-1, _('Header cannot be opened or does not match %s, %s.') % (name, arch))
    return
    

def checkRpmMD5(package, urlgraberror=0):
    """take a package, check it out by trying to open it, return 1 if it's good
       return 0 if it's not"""
    ts.sigChecking('md5')
    fdno = os.open(package, os.O_RDONLY)
    try:
        ts.hdrFromFdno(fdno)
    except rpm.error, e:
        good = 0
    else:
        good = 1
    os.close(fdno)
    ts.sigChecking('default')

    if urlgraberror:
        if not good:
            raise URLGrabError(-1, _('RPM %s fails md5 check') % (package)) 
        else:
            return
    else:
        return good

def checkSig(package):
    """ take a package, check it's sigs, return 0 if they are all fine, return 
    1 if the gpg key can't be found,  2 if the header is in someway damaged,
    3 if the key is not trusted, 4 if the pkg is not gpg or pgp signed"""
    ts.sigChecking('default')
    fdno = os.open(package, os.O_RDONLY)
    try:
        hdr = ts.hdrFromFdno(fdno)
    except rpm.error, e:
        if str(e) == "public key not availaiable":
            return 1
        if str(e) == "public key not available":
            return 1
        if str(e) == "public key not trusted":
            return 3
        if str(e) == "error reading package header":
            return 2
    else:
        error, siginfo = getSigInfo(hdr)
        if error == 101:
            os.close(fdno)
            del hdr
            return 4
        else:
            del hdr
    os.close(fdno)
    return 0

def getSigInfo(hdr):
    """checks if a computerhand back signature information and an error code"""
    string = '%|DSAHEADER?{%{DSAHEADER:pgpsig}}:{%|RSAHEADER?{%{RSAHEADER:pgpsig}}:{%|SIGGPG?{%{SIGGPG:pgpsig}}:{%|SIGPGP?{%{SIGPGP:pgpsig}}:{(none)}|}|}|}|'
    siginfo = hdr.sprintf(string)
    if siginfo != '(none)':
        error = 0 
        sigtype, sigdate, sigid = siginfo.split(',')
    else:
        error = 101
        sigtype = 'MD5'
        sigdate = 'None'
        sigid = 'None'
        
    infotuple = (sigtype, sigdate, sigid)
    return error, infotuple

def getProvides(header):
    provnames = []
    provides = header[rpm.RPMTAG_PROVIDENAME]
    if provides is None:
        pass
    elif type(provides) is types.ListType:
        provnames.extend(provides)
    else:
        provnames.append(provides)
    return provnames
    
def compareEVR((e1, v1, r1), (e2, v2, r2)):
    # return 1: a is newer than b 
    # 0: a and b are the same version 
    # -1: b is newer than a 
    def rpmOutToStr(arg):
        if type(arg) != types.StringType and arg != None:
            arg = str(arg)
        return arg
    e1 = rpmOutToStr(e1)
    v1 = rpmOutToStr(v1)
    r1 = rpmOutToStr(r1)
    e2 = rpmOutToStr(e2)
    v2 = rpmOutToStr(v2)
    r2 = rpmOutToStr(r2)
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    log(6, '%s, %s, %s vs %s, %s, %s = %s' % (e1, v1, r1, e2, v2, r2, rc))
    return rc
    

def formatRequire (name, version, flags):
    if flags:
        if flags & (rpm.RPMSENSE_LESS | rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL):
            name = name + ' '
        if flags & rpm.RPMSENSE_LESS:
            name = name + '<'
        if flags & rpm.RPMSENSE_GREATER:
            name = name + '>'
        if flags & rpm.RPMSENSE_EQUAL:
            name = name + '='
            name = name + ' %s' % version
    return name


def openrpmdb():
    try:
        db = rpm.TransactionSet(conf.installroot)
    except rpm.error, e:
        errorlog(0, _("Could not open RPM database for reading. Perhaps it is already in use?"))
    return db


# this is done to make the hdr writing _more_ sane for rsync users especially
__all__ = ["GzipFile","open"]

class GzipFile(gzip.GzipFile):
    def _write_gzip_header(self):
        self.fileobj.write('\037\213')             # magic header
        self.fileobj.write('\010')                 # compression method
        fname = self.filename[:-3]
        flags = 0
        if fname:
            flags = FNAME
        self.fileobj.write(chr(flags))
        write32u(self.fileobj, long(0))
        self.fileobj.write('\002')
        self.fileobj.write('\377')
        if fname:
            self.fileobj.write(fname + '\000')


def _gzipOpen(filename, mode="rb", compresslevel=9):
    return GzipFile(filename, mode, compresslevel)

class RPM_Base_Work:
    def __init__(self):
        self.hdr = None

    def _getTag(self, tag):
        if self.hdr is None:
            errorlog(0, _('Got an empty Header, something has gone wrong'))
            #FIXME should raise a yum error here
            sys.exit(1)
        return self.hdr[tag]
    
    def isSource(self):
        if self._getTag('sourcepackage') == 1:
            return 1
        else:
            return 0
        
    def name(self):
        return self._getTag('name')
        
    def arch(self):
        return self._getTag('arch')
        
    def epoch(self):
        return self._getTag('epoch')
    
    def version(self):
        return self._getTag('version')
        
    def release(self):
        return self._getTag('release')
        
    def evr(self):
        e = self._getTag('epoch')
        v = self._getTag('version')
        r = self._getTag('release')
        return (e, v, r)
        
    def nevra(self):
        n = self._getTag('name')
        e = self._getTag('epoch')
        v = self._getTag('version')
        r = self._getTag('release')
        a = self._getTag('arch')
        return (n, e, v, r, a)
    
    def writeHeader(self, headerdir, compress):
    # write the header out to a file with the format: name-epoch-ver-rel.arch.hdr
    # return the name of the file it just made - no real reason :)
        (name, epoch, ver, rel, arch) = self.nevra()
        if epoch is None:
            epoch = '0'
        if self.isSource():
            headerfn = "%s/%s-%s-%s-%s.src.hdr" % (headerdir, name, epoch, ver, rel)
        else:
            headerfn = "%s/%s-%s-%s-%s.%s.hdr" % (headerdir, name, epoch, ver, rel, arch)

        if compress:
            headerout = _gzipOpen(headerfn, "w")
        else:
            headerout = open(headerfn, "w")
        headerout.write(self.hdr.unload(1))
        headerout.close()
        return(headerfn)

class Header_Work(RPM_Base_Work):
    """for operating on hdrs in and out of the rpmdb
       if the first arg is a string then it's a filename
       otherwise it's an rpm hdr"""
    def __init__(self, header):
        if type(header) is types.StringType:
            try:
                fd = gzip.open(header, 'r')
                try: 
                    h = rpm.headerLoad(fd.read())
                except rpm.error, e:
                    errorlog(0,_('Damaged Header %s') % header)
                    h = None
            except IOError,e:
                fd = open(header, 'r')
                try:
                    h = rpm.headerLoad(fd.read())
                except rpm.error, e:
                    errorlog(0,_('Damaged Header %s') % header)
                    h = None
            except ValueError, e:
                errorlog(0,_('Damaged Header %s') % header)
                h = None
            except zlibError, e:
                errorlog(0,_('Damaged Header %s') % header)
                h = None
            fd.close()
        else:
            h = header
        self.hdr = h


class RPM_Work(RPM_Base_Work):
    def __init__(self, rpmfn):
        ts.setVSFlags(~(rpm._RPMVSF_NOSIGNATURES))
        fd = os.open(rpmfn, os.O_RDONLY)
        try:
            self.hdr = ts.hdrFromFdno(fd)
        except rpm.error, e:
            errorlog(0, _('Error opening rpm %s - error %s') % (rpmfn, e))
            self.hdr = None
        os.close(fd)
    
class Rpm_Ts_Work:
    """This should operate on groups of headers/matches/etc in the rpmdb - ideally it will 
    operate with a list of the Base objects above, so I can refer to any one object there
    not sure the best way to do this yet, more thinking involved"""
    def __init__(self, dbPath='/'):
        try:
            if conf.installroot:
                if conf.installroot != '/':
                    dbPath = conf.installroot
        except NameError, e:
            pass

        self.ts = rpm.TransactionSet(dbPath)
        
        self.methods = ['addInstall', 'addErase', 'run', 'check', 'order', 'hdrFromFdno',
                   'closeDB', 'dbMatch', 'setFlags', 'setVSFlags', 'setProbFilter']
                   
    def __getattr__(self, attribute):
        if attribute in self.methods:
            return getattr(self.ts, attribute)
        else:
            raise AttributeError, attribute
            
    def match(self, tag = None, search = None, mire = None):
        """hands back a list of Header_Work objects"""
        hwlist = []
        # hand back the whole list of hdrs
        if mire is None and tag is None and search is None:
            hdrlist = self.ts.dbMatch()
            
        else:
            #just do a non-mire'd search
            if mire == None:
                hdrlist = self.ts.dbMatch(tag, search)
            else:
                # mire search
                if mire == 'glob':
                    hdrlist = self.ts.dbMatch()
                    hdrlist.pattern(tag, rpm.RPMMIRE_GLOB, search)
                elif mire == 'regex':
                    hdrlist = self.ts.dbMatch()
                    hdrlist.pattern(tag, rpm.RPMMIRE_REGEX, search)
                elif mire == 'strcmp':
                    hdrlist = self.ts.dbMatch()
                    hdrlist.pattern(tag, rpm.RPMMIRE_STRCMP, search)
                else:
                    hdrlist = self.ts.dbMatch()
                    hdrlist.pattern(tag, rpm.RPMMIRE_DEFAULT, search)
        
        for hdr in hdrlist:
            hdrobj = Header_Work(hdr)
            hwlist.append(hdrobj)
        return hwlist
    
    def sigChecking(self, sig):
        """pass type of check you want to occur, default is to have them off"""
        if sig == 'md5':
            #turn off everything but md5 - and we need to the check the payload
            self.ts.setVSFlags(~(rpm.RPMVSF_NOMD5|rpm.RPMVSF_NEEDPAYLOAD))
        elif sig == 'none':
            # turn off everything - period
            self.ts.setVSFlags(~(rpm._RPMVSF_NOSIGNATURES))
        elif sig == 'default':
            # set it back to the default
            self.ts.setVSFlags(rpm.RPMVSF_DEFAULT)
        else:
            raise AttributeError, sig
