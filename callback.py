#!/usr/bin/python -t
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2002 Duke University 

import rpm, os, sys

callbackfilehandles = {}
def install_callback(what, bytes, total, h, user):
	if what == rpm.RPMCALLBACK_TRANS_PROGRESS:
		#callback("rpm", what, (bytes, total), (h, user))
		#print "what = TRANS_PROG"
		#print "op: %d" % bytes
		#print "total ops  %s" % total
		#if h != None:
		#	print h[rpm.RPMTAG_NAME]
		#else:
		#	print "No header yet"
		#print user
		pass
	elif what == rpm.RPMCALLBACK_TRANS_STOP:
		#callback("rpm", what, (bytes, total), (h, user))
		#print "what = TRANS_STOP"
		#print "bytes %s" % bytes
		#print "total %s" % total
		#if h != None:
		#	print h[rpm.RPMTAG_NAME]
		#else:
		#	print "No header yet"
		#print user
		#print "op: %s" % bytes
		pass

	elif what == rpm.RPMCALLBACK_TRANS_START:
		#callback("rpm", what, (bytes, total), (h, user))
		#print "what = TRANS_START"
		#print "bytes %s" % bytes
		#print "total %s" % total
		#if h != None:
		#	print h[rpm.RPMTAG_NAME]
		pass
	elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
		if h != None:
			#print bytes
			#print total
			pkg, rpmloc = h
			fd = os.open(rpmloc, os.O_RDONLY)
			callbackfilehandles[h]=fd
			return fd
		else:
			print "No header - huh?"
  
	elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
		#callback("rpm", what, (bytes, total), (h, user))
		os.close(callbackfilehandles[h])
		fd = 0

	elif what == rpm.RPMCALLBACK_INST_PROGRESS:
		#self.callback("rpm", what, (bytes, total), (h, user))
		if h != None:
			pkg, rpmloc = h
			percent = (bytes*100L)/total
			sys.stdout.write("\r%s %d %% done" % (pkg[rpm.RPMTAG_NAME], percent))
			if bytes == total:
				print " "
			
      
    