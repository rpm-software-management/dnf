#!/usr/bin/python

import sys
sys.path.insert(0, '/home/skvidal/cvs/yum-HEAD')

import yummain
try:
    yummain.main(sys.argv[1:])
except KeyboardInterrupt, e:
    print >> sys.stderr, "\n\nExiting on user cancel."
    sys.exit(1)
                                
