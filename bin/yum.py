#!/usr/bin/python
import sys
try:
   import yum
except ImportError:
   print >> sys.stderr, "The yum libraries do not seem to be available\
on your system for this version of python ", sys.version
   print >> sys.stderr, "Please make sure the package you used to install\
yum was built for your install of python."
   sys.exit(1)

sys.path.insert(0, '/usr/share/yum-cli')
try:
    import yummain
    yummain.main(sys.argv[1:])
except KeyboardInterrupt, e:
    print >> sys.stderr, "\n\nExiting on user cancel."
    sys.exit(1)
