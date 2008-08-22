#! /usr/bin/python -tt

# This is a simple command to check that "Is this ok [y/N]: " and yes and no
# have either all been translated or none have been translated.

import sys
import glob

from yum.misc import to_utf8

def trans(msg, default):
    if msg == 'msgstr ""\n':
        return unicode(default, encoding='utf-8')
    if msg.startswith('msgstr "'):
        msg = msg[len('msgstr "'):]
        msg = msg[:-2]
    return unicode(msg, encoding='utf-8')

for fname in glob.glob("po/*.po"):
    next = None
    is_this_ok  = None
    sis_this_ok = None
    yes         = None
    syes        = None
    y           = None
    sy          = None
    no          = None
    sno         = None
    n           = None
    sn          = None
    for line in file(fname):
        if next is not None:
            if next == 'is_this_ok':
                sis_this_ok = line
                if line == 'msgstr ""\n' or line.find('[y/N]') != -1:
                    is_this_ok = False
                else:
                    is_this_ok = True
            if next == 'yes':
                syes = line
                yes  = line != 'msgstr ""\n'
            if next == 'y':
                sy   = line
                y    = line != 'msgstr ""\n'
            if next == 'no':
                sno  = line
                no   = line != 'msgstr ""\n'
            if next == 'n':
                sn   = line
                n    = line != 'msgstr ""\n'
            next = None
            continue
        if line == 'msgid "Is this ok [y/N]: "\n':
            next = 'is_this_ok'
        if line == 'msgid "yes"\n':
            next = 'yes'
        if line == 'msgid "y"\n':
            next = 'y'
        if line == 'msgid "no"\n':
            next = 'no'
        if line == 'msgid "n"\n':
            next = 'n'
    if (is_this_ok is None or
        yes is None or
        y   is None or
        no  is None or
        n   is None):
        print >>sys.stderr, """\
ERROR: Can't find all the msg id's in %s
is_this_ok %s
yes %s
y   %s
no  %s
n   %s
""" % (fname,
       is_this_ok is None,
       yes is None,
       y   is None,
       no  is None,
       n   is None)
        sys.exit(1)
    syes = trans(syes, "yes")
    sy   = trans(sy,   "y")
    sno  = trans(sno,  "no")
    sn   = trans(sn,   "n")
    if (is_this_ok != yes or
        is_this_ok != no):
        print >>sys.stderr, """\
ERROR: yes/no translations don't match in: %s
is_this_ok %5s: %s
yes        %5s: %s
y          %5s: %s
no         %5s: %s
n          %5s: %s
""" % (fname,
       to_utf8(is_this_ok), to_utf8(sis_this_ok),
       to_utf8(yes), to_utf8(syes), to_utf8(y), to_utf8(sy),
       to_utf8(no), to_utf8(sno), to_utf8(n), to_utf8(sn))
    if syes[0] != sy:
        print >>sys.stderr, """\
ERROR: yes/y translations don't match in: %s
yes        %5s: %s
y          %5s: %s
""" % (fname,
       yes, syes, y, sy)
    if sno[0] != sn:
        print >>sys.stderr, """\
ERROR: no/n translations don't match in: %s
no         %5s: %s
n          %5s: %s
""" % (fname,
       no, sno, n, sn)
