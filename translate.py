# Python module to handle translations
#
# Shamlessly copied from the anaconda tree.
# $Id$

import os, string

prefix = '/usr'
localedir = prefix + '/share/locale'
_cat = None
_cats = {}

# What languages do we support?
lang = []

def _expandLang(str):
    langs = [str]
    # remove charset ...
    if '.' in str:
        langs.append(string.split(str, '.')[0])
        # also add 2 character language code ...
    if len(str) > 2:
        langs.append(str[:2])
    return langs

def _readEnvironment():
    global lang
    for env in 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG':
        if os.environ.has_key(env):
            lang = string.split(os.environ[env], ':')
            lang = map(_expandLang, lang)
            lang = reduce(lambda a, b: a + b, lang)
            break
    # remove duplicates
    newlang = []
    for l in lang:
        if not l in newlang:
            newlang.append(l)
    lang = newlang
    del newlang
    
if 'C' not in lang:
    lang.append('C')

error = 'gettext.error'

def _lsbStrToInt(str):
    return ord(str[0]) + \
           (ord(str[1]) << 8) + \
           (ord(str[2]) << 16) + \
           (ord(str[3]) << 24)
def _intToLsbStr(int):
    return chr(int         & 0xff) + \
           chr((int >> 8)  & 0xff) + \
           chr((int >> 16) & 0xff) + \
           chr((int >> 24) & 0xff)
def _msbStrToInt(str):
    return ord(str[3]) + \
           (ord(str[2]) << 8) + \
           (ord(str[1]) << 16) + \
           (ord(str[0]) << 24)
def _intToMsbStr(int):
    return chr((int >> 24) & 0xff) + \
           chr((int >> 16) & 0xff) + \
           chr((int >> 8) & 0xff) + \
           chr(int & 0xff)
def _StrToInt(str):
    if _gettext_byteorder == 'msb':
        return _msbStrToInt(str)
    else:
        return _lsbStrToInt(str)
def _intToStr(int):
    if _gettext_byteorder == 'msb':
        return _intToMsbStr(str)
    else:
        return _intToLsbStr(str)

def _getpos(levels = 0):
    """Returns the position in the code where the function was called.
    The function uses some knowledge about python stack frames."""
    import sys
    # get access to the stack frame by generating an exception.
    try:
        raise RuntimeError
    except RuntimeError:
        frame = sys.exc_traceback.tb_frame
    frame = frame.f_back # caller's frame
    while levels > 0:
        frame = frame.f_back
        levels = levels - 1
    return (frame.f_globals['__name__'],
            frame.f_code.co_name,
            frame.f_lineno)

class Catalog:
    def __init__(self, domain=None, localedir=localedir):
        self.domain = domain
        self.localedir = localedir
        self.cat = {}
        if not domain: return
        for self.lang in lang:
            if self.lang == 'C':
                return
            catalog = "%s/%s/LC_MESSAGES/%s.mo" % (
                    localedir, self.lang, domain)
            try:
                f = open(catalog, "r")
                buffer = f.read()
                f.close()
                del f
                break
            except IOError:
                pass
        else:
            return # assume C locale

        if _StrToInt(buffer[:4]) != 0x950412de:
            # magic number doesn't match
            raise error, 'Bad magic number in %s' % (catalog,)

        self.revision = _StrToInt(buffer[4:8])
        nstrings = _StrToInt(buffer[8:12])
        origTabOffset  = _StrToInt(buffer[12:16])
        transTabOffset = _StrToInt(buffer[16:20])
        for i in range(nstrings):
            origLength = _StrToInt(buffer[origTabOffset:
                                          origTabOffset+4])
            origOffset = _StrToInt(buffer[origTabOffset+4:
                                          origTabOffset+8])
            origTabOffset = origTabOffset + 8
            origStr = buffer[origOffset:origOffset+origLength]

            transLength = _StrToInt(buffer[transTabOffset:
                                           transTabOffset+4])
            transOffset = _StrToInt(buffer[transTabOffset+4:
                                           transTabOffset+8])
            transTabOffset = transTabOffset + 8
            transStr = buffer[transOffset:transOffset+transLength]

            self.cat[origStr] = transStr

    def gettext(self, string):
        """Get the translation of a given string"""
        if self.cat.has_key(string):
            return self.cat[string]
        else:
            return string
    # allow catalog access as cat(str) and cat[str] and cat.gettext(str)
    __getitem__ = gettext
    __call__ = gettext

    # this is experimental code for producing mo files from Catalog objects
    def __setitem__(self, string, trans):
        """Set the translation of a given string"""
        self.cat[string] = trans
    def save(self, file):
        """Create a .mo file from a Catalog object"""
        try:
            f = open(file, "wb")
        except IOError:
            raise error, "can't open " + file + " for writing"
        f.write(_intToStr(0x950412de))    # magic number
        f.write(_intToStr(0))             # revision
        f.write(_intToStr(len(self.cat))) # nstrings

        oIndex = []; oData = ''
        tIndex = []; tData = ''
        for orig, trans in self.cat.items():
            oIndex.append((len(orig), len(oData)))
            oData = oData + orig + '\0'
            tIndex.append((len(trans), len(tData)))
            tData = tData + trans + '\0'
        oIndexOfs = 20
        tIndexOfs = oIndexOfs + 8 * len(oIndex)
        oDataOfs = tIndexOfs + 8 * len(tIndex)
        tDataOfs = oDataOfs + len(oData)
        f.write(_intToStr(oIndexOfs))
        f.write(_intToStr(tIndexOfs))
        for length, offset in oIndex:
            f.write(_intToStr(length))
            f.write(_intToStr(offset + oDataOfs))
        for length, offset in tIndex:
            f.write(_intToStr(length))
            f.write(_intToStr(offset + tDataOfs))
        f.write(oData)
        f.write(tData)

def bindtextdomain(domain, localedir=localedir):
    global _cat
    if not _cats.has_key(domain):
        _cats[domain] = Catalog(domain, localedir)
    if not _cat: _cat = _cats[domain]

def textdomain(domain):
    global _cat
    if not _cats.has_key(domain):
        _cats[domain] = Catalog(domain)
    _cat = _cats[domain]

def gettext(string):
    if _cat == None: raise error, "No catalog loaded"
    return _cat.gettext(string)

def dgettext(domain, string):
    if domain is None:
        return gettext(string)
    if not _cats.has_key(domain):
        raise error, "Domain '" + domain + "' not loaded"
    return _cats[domain].gettext(string)

def test():
    import sys
    global localedir
    if len(sys.argv) not in (2, 3):
        print "Usage: %s DOMAIN [LOCALEDIR]" % (sys.argv[0],)
        sys.exit(1)
    domain = sys.argv[1]
    if len(sys.argv) == 3:
        bindtextdomain(domain, sys.argv[2])
    textdomain(domain)
    info = gettext('')  # this is where special info is often stored
    if info:
        print "Info for domain %s, lang %s." % (domain, _cat.lang)
        print info
    else:
        print "No info given in mo file."

def getlangs():
    global lang
    return lang

def setlangs(newlang):
    global lang
    lang = newlang
    if type(newlang) == type(""):
        lang = [ newlang ]
    for l in lang:
        langs = _expandLang(l)
        for nl in langs:
            if not nl in lang:
                lang.append(nl)
    return lang

def getArch ():
    arch = os.uname ()[4]
    if (len (arch) == 4 and arch[0] == 'i' and arch[2:4] == "86"):
        arch = "i386"

    if arch == "sparc64":
        arch = "sparc"

    return arch

###################################################################
# Now the real module code

if getArch() == 'sparc':
    _gettext_byteorder = 'msb'
else:
    _gettext_byteorder = 'lsb'

class i18n:
    def __init__(self):
        self.langs = lang
        self.cat = Catalog("yum")

    def getlangs(self):
        return self.langs

    def setlangs(self, langs):
        self.langs = setlangs(langs)
        self.cat = Catalog("yum")

    def gettext(self, string):
        return self.cat.gettext(string)

def N_(str):
    return str

_readEnvironment()
cat = i18n()
_ = cat.gettext
