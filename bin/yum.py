#!/usr/bin/python

import sys
sys.path.insert(0, '/usr/share/yum-cli')

import yummain
try:
    yummain.main(sys.argv[1:])
except KeyboardInterrupt, e:
    print >> sys.stderr, "\n\nExiting on user cancel."
    sys.exit(1)
                                
