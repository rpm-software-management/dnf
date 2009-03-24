#! /usr/bin/python -tt

import yum, os, sys, time, gc
from urlgrabber.progress import format_number

def out_mem(pid):
    ps = {}
    for line in open("/proc/%d/status" % pid):
        if line[-1] != '\n':
            continue
        data = line[:-1].split(':\t', 1)
        if data[1].endswith(' kB'):
            data[1] = data[1][:-3]
        ps[data[0].strip().lower()] = data[1].strip()
    if 'vmrss' in ps and 'vmsize' in ps:
        print "* Memory : %5s RSS (%5sB VSZ)" % \
                    (format_number(int(ps['vmrss']) * 1024),
                     format_number(int(ps['vmsize']) * 1024))

out_mem(os.getpid())
while True:
    yb = yum.YumBase()
    yb.repos.setCacheDir(yum.misc.getCacheDir())
    yb.rpmdb.returnPackages()
    yb.pkgSack.returnPackages()
    out_mem(os.getpid())
    time.sleep(4)

    if False:
       del yb
       print len(gc.garbage)
       if gc.garbage:
           print gc.garbage[0]
           print gc.get_referrers(gc.garbage[0])
    # print "DBG:", gc.get_referrers(yb)
