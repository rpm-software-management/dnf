#!/usr/bin/python -tt
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
# Copyright 2003 Duke University

# classes for parsing the metadata files for the new metadata format


# used with python -i :)
import sys
import os
import time
import rpm
import packageSack
import packageObject
import repoMDObject
import mdUtils
import mdErrors


def process(current, total, name=None):
    sys.stdout.write('\r' + ' ' * 80)
    sys.stdout.write('\rNode %d of %d' % (current, total))
    sys.stdout.flush()

if len(sys.argv) < 4:
    print 'test.py: /path/to/repo /other/repo somepackagename'
    sys.exit(1)
   
print time.time()
repos = sys.argv[1:3]
pkgSack = packageSack.XMLPackageSack(packageObject.RpmXMLPackageObject)
numid = 0
for repo in repos:
    numid+=1
    basepath = repo
    repomdxmlfile = os.path.join(basepath, 'repodata/repomd.xml')
    repoid = repo

    try:
        repodata = repoMDObject.RepoMD(repoid, repomdxmlfile)
    except mdErrors.RepoMDError, e:
        print >> sys.stderr, e
        sys.exit(1)
    
    (pbase, phref) = repodata.primaryLocation()
    (fbase, fhref) = repodata.filelistsLocation()
    (obase, ohref) = repodata.otherLocation()
    
    
    processlist = [phref]
    for file in processlist:
        print time.time()
        print 'importing %s from %s' % (file, repoid)
        complete = basepath + '/' + file
        try:
            pkgSack.addFile(repoid, complete, process)
        except mdErrors.PackageSackError, e:
            print >> sys.stderr, e
            sys.exit(1)
            
    print ' '
    print time.time()

for pkg in pkgSack.searchNevra(sys.argv[3]):
    print pkg
    for reqtup in pkg.returnPrco('requires'):
        (reqn, reqf, (reqe,reqv,reqr)) = reqtup
        # rpmlib deps should be handled on their own
        if reqn[:6] == 'rpmlib':
            continue
        # kill self providers, too
        if pkg.checkPrco('provides', reqtup):
            continue
            
        # get a list of all pkgs that match the reqn
        providers = pkgSack.searchProvides(reqn)
        if len(providers) == 0:
            print 'unresolved: %s  %s %s:%s-%s' % (reqn, reqf, reqe, reqv, reqr)
            continue

        if len(providers) == 1:
            if reqf is None:
                print '%s: %s from %s' % (reqn, providers[0], providers[0].returnSimple('relativepath'))
                continue

            # only one entry but we need to match out it out
            if providers[0].checkPrco('provides', reqtup):
                print '%s: %s from %s' % (reqn, providers[0], providers[0].returnSimple('relativepath'))
                continue

        
        output = '%s:' % reqn
        for prov in providers:
            if reqf is not None:
                if prov.checkPrco('provides', reqtup):
                    output = output + '||' + prov.__str__()
                else:
                    print '%s does not provide %s %s %s %s %s' % (prov, reqn, reqf, reqe, reqv, reqr)                
            else:
                output = output + '||' + prov.__str__()
                
        print output
print time.time()

