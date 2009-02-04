#! /usr/bin/python -tt

import yum, os, sys, time, gc

while True:
    yb = yum.YumBase()
    yb.repos.setCacheDir(yum.misc.getCacheDir())
    yb.rpmdb.returnPackages()
    yb.pkgSack.returnPackages()
    time.sleep(4)
    # print "DBG:", gc.get_referrers(yb)
