#! /usr/bin/python -tt

import sys
import yum

__provides_of_requires_exact__ = False

yb1 = yum.YumBase()
yb1.conf.cache = True
yb2 = yum.YumBase()
yb2.conf.cache = True

if len(sys.argv) > 1 and sys.argv[1].lower() == 'full':
    print "Doing full test"
    __provides_of_requires_exact__ = True

assert hasattr(yb1.rpmdb, '__cache_rpmdb__')
yb1.rpmdb.__cache_rpmdb__ = False
yb2.setCacheDir()

# Version
ver1 = yb1.rpmdb.simpleVersion(main_only=True)[0]
ver2 = yb2.rpmdb.simpleVersion(main_only=True)[0]
if ver1 != ver2:
    print >>sys.stderr, "Error: Version mismatch:", ver1, ver2

# Conflicts
cpkgs1 = yb1.rpmdb.returnConflictPackages()
cpkgs2 = yb2.rpmdb.returnConflictPackages()
if len(cpkgs1) != len(cpkgs2):
    print >>sys.stderr, "Error: Conflict len mismatch:", len(cpkgs1),len(cpkgs2)
for pkg in cpkgs1:
    if pkg not in cpkgs2:
        print >>sys.stderr, "Error: Conflict cache missing", pkg
for pkg in cpkgs2:
    if pkg not in cpkgs1:
        print >>sys.stderr, "Error: Conflict cache extra", pkg

# File Requires
frd1, blah, fpd1 = yb1.rpmdb.fileRequiresData()
frd2, blah, fpd2 = yb2.rpmdb.fileRequiresData()
if len(frd1) != len(frd2):
    print >>sys.stderr, "Error: FileReq len mismatch:", len(frd1), len(frd2)
for pkgtup in frd1:
    if pkgtup not in frd2:
        print >>sys.stderr, "Error: FileReq cache missing", pkgtup
        continue
    if len(set(frd1[pkgtup])) != len(set(frd2[pkgtup])):
        print >>sys.stderr, ("Error: FileReq[%s] len mismatch:" % (pkgtup,),
                             len(frd1[pkgtup]), len(frd2[pkgtup]))
    for name in frd1[pkgtup]:
        if name not in frd2[pkgtup]:
            print >>sys.stderr, ("Error: FileReq[%s] cache missing" % (pkgtup,),
                                 name)
for pkgtup in frd2:
    if pkgtup not in frd1:
        print >>sys.stderr, "Error: FileReq cache extra", pkgtup
        continue
    for name in frd2[pkgtup]:
        if name not in frd1[pkgtup]:
            print >>sys.stderr, ("Error: FileReq[%s] cache extra" % (pkgtup,),
                                 name)

# File Provides (of requires) -- not exact
if len(fpd1) != len(fpd2):
    print >>sys.stderr, "Error: FileProv len mismatch:", len(fpd1), len(fpd2)
for name in fpd1:
    if name not in fpd2:
        print >>sys.stderr, "Error: FileProv cache missing", name
        continue

    if not __provides_of_requires_exact__:
        continue # We might be missing some providers

    if len(fpd1[name]) != len(fpd2[name]):
        print >>sys.stderr, ("Error: FileProv[%s] len mismatch:" % (pkgtup,),
                             len(fpd1[name]), len(fpd2[name]))
    for pkgtup in fpd1[name]:
        if pkgtup not in fpd2[name]:
            print >>sys.stderr,"Error: FileProv[%s] cache missing" % name,pkgtup
for name in fpd2:
    if name not in fpd1:
        print >>sys.stderr, "Error: FileProv cache extra", name
        continue
    for pkgtup in fpd2[name]:
        if pkgtup not in fpd1[name]:
            print >>sys.stderr,"Error: FileProv[%s] cache extra" % name,pkgtup
