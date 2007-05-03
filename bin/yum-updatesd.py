#!/usr/bin/python
import sys, os
import optparse

parser = optparse.OptionParser()
parser.add_option("-f", "--no-fork", action="store_true", default=False, dest="nofork")
parser.add_option("-r", "--remote-shutdown", action="store_true", default=False, dest="remoteshutdown")    
(options, args) = parser.parse_args()

if not options.nofork:
    if os.fork():
        sys.exit()
    fd = os.open("/dev/null", os.O_RDWR)
    os.dup2(fd, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.close(fd)

sys.path.insert(0, '/usr/share/yum-cli')
try:
    import yumupd
    yumupd.main(options)
except KeyboardInterrupt, e:
    print >> sys.stderr, "\n\nExiting on user cancel."
    sys.exit(1)
