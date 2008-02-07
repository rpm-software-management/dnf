#!/usr/bin/env python
"""i18n abstraction

License: GPL
Author: Vladimir Bormotov <bor@vb.dn.ua>

$Id$
"""
# $RCSfile$
__version__ = "$Revision$"[11:-2]
__date__ = "$Date$"[7:-2]

import types

def _toUTF( txt ):
    """ this function convert a string to unicode"""
    rc=""
    if isinstance(txt,types.UnicodeType):
        return txt
    else:
        try:
            rc = unicode( txt, 'utf-8' )
        except UnicodeDecodeError, e:
            rc = unicode( txt, 'iso-8859-1' )
        return rc

_transfn = None

def _translate(txt):
    txt = _transfn(txt)
    return _toUTF(txt)
    
    

try: 
    import gettext
    import sys
    if sys.version_info[0] == 2:
        t = gettext.translation('yum')
        _transfn = t.gettext
    else:
        gettext.bindtextdomain('yum', '/usr/share/locale')
        gettext.textdomain('yum')
        _transfn = gettext.gettext
    _ = _translate
    
except:
    def _(str):
        """pass given string as-is"""
        return str

if __name__ == '__main__':
    pass

# vim: set ts=4 et :
