#!/usr/bin/env python
"""i18n abstraction

License: GPL
Author: Vladimir Bormotov <bor@vb.dn.ua>

$Id$
"""
# $RCSfile$
__version__ = "$Revision$"[11:-2]
__date__ = "$Date$"[7:-2]

try: 
    import gettext
    import sys
    if sys.version_info[0] == 2:
        t = gettext.translation('yum')
        _ = t.gettext
    else:
        gettext.bindtextdomain('yum', '/usr/share/locale')
        gettext.textdomain('yum')
        _ = gettext.gettext

except:
    def _(str):
        """pass given string as-is"""
        return str

if __name__ == '__main__':
    pass

# vim: set ts=4 et :
