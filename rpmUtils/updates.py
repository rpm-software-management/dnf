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
# Copyright 2004 Duke University

import rpmUtils.miscutils
import rpmUtils.arch
import rpmUtils

class Updates:
    """This class computes and keeps track of updates and obsoletes.
       initialize, add installed packages, add available packages (both as
       unique lists of name, epoch, ver, rel, arch tuples), add an optional dict
       of obsoleting packages with obsoletes and what they obsolete ie:
        foo, i386, 0, 1.1, 1: bar >= 1.1."""

    def __init__(self, instlist, availlist):
        self.changeTup = [] # storage list tuple of updates or obsoletes
                            # (oldpkg, newpkg, ['update'|'obsolete'])

        self.installed = instlist # list of installed pkgs (n, a, e, v, r)
        self.available = availlist # list of available pkgs (n, a, e, v, r)
        self.rawobsoletes = {} # dict of obsoleting package->[what it obsoletes]
        self.exactarch = 1 # don't change archs by default
        self.exactarchlist = ['kernel', 'kernel-smp', 'glibc', 'kernel-hugemem',
                              'kernel-enterprise', 'kernel-bigmem', 'kernel-BOOT']
                              
        self.myarch = rpmUtils.arch.getCanonArch() # this is for debugging only 
                                                   # set this if you want to 
                                                   # test on some other arch
                                                   # otherwise leave it alone
        
        # make some dicts from installed and available
        self.installdict = self.makeNADict(self.installed, 1)
        self.availdict = self.makeNADict(self.available, 1)

        # holder for our updates dict
        self.updatesdict = {}
        #debug, ignore me
        self.debug = 0

    def debugprint(self, msg):
        if self.debug:
            print msg
        
    def makeNADict(self, pkglist, Nonelists):
        """return lists of (e,v,r) tuples as value of a dict keyed on (n, a)
            optionally will return a (n, None) entry with all the a for that
            n in tuples of (a,e,v,r)"""
            
        returndict = {}
        for (n, a, e, v, r) in pkglist:
            if not returndict.has_key((n, a)):
                returndict[(n, a)] = []
            returndict[(n, a)].append((e,v,r))

            if Nonelists:
                if not returndict.has_key((n, None)):
                    returndict[(n, None)] = []
                returndict[(n, None)].append((a, e, v, r))
            
        return returndict
                    

    def returnNewest(self, evrlist):
        """takes a list of (e, v, r) tuples and returns the newest one"""
        if len(evrlist)==0:
            raise rpmUtils.RpmUtilsError, "Zero Length List in returnNewest call"
            
        if len(evrlist)==1:
            return evrlist[0]
        
        (new_e, new_v, new_r) = evrlist[0] # we'll call the first ones 'newest'
        
        for (e, v, r) in evrlist[1:]:
            rc = rpmUtils.miscutils.compareEVR((e, v, r), (new_e, new_v, new_r))
            if rc > 0:
                new_e = e
                new_v = v
                new_r = r
        return (new_e, new_v, new_r)
         

    def returnHighestVerFromAllArchsByName(self, name, archlist, pkglist):
        """returns a list of package tuples in a list (n, a, e, v, r)
           takes a package name, a list of archs, and a list of pkgs in
           (n, a, e, v, r) form."""
        # go through list and throw out all pkgs not in archlist
        matchlist = []
        for (n, a, e, v, r) in pkglist:
            if name == n:
                if a in archlist:
                    matchlist.append((n, a, e, v, r))

        if len(matchlist) == 0:
            return []
            
        # get all the evr's in a tuple list for returning the highest
        verlist = []
        for (n, a, e, v, r) in matchlist:
            verlist.append((e,v,r))

        (high_e, high_v, high_r) = self.returnNewest(verlist)
            
        returnlist = []
        for (n, a, e, v, r) in matchlist:
            if (high_e, high_v, high_r) == (e, v, r):
                returnlist.append((n,a,e,v,r))
                
        return returnlist
           
    def condenseUpdates(self):
        """remove any accidental duplicates in updates"""
        
        for tup in self.updatesdict.keys():
            if len(self.updatesdict[tup]) > 1:
                mylist = self.updatesdict[tup]
                self.updatesdict[tup] = rpmUtils.miscutils.unique(mylist)
    
    
    def checkForObsolete(self, pkglist, newest=1):
        """accept a list of packages to check to see if anything obsoletes them
           return an obsoleted_dict in the format of makeObsoletedDict"""
           
        obsdict = {} # obseleting package -> [obsoleted package]
        pkgdict = self.makeNADict(pkglist, 1)
        
        # this needs to keep arch in mind
        # if foo.i386 obsoletes bar
        # it needs to obsoletes bar.i386 preferentially, not bar.x86_64
        # if there is only one bar and only one foo then obsolete it, but try to
        # match the arch.
        
        # look through all the obsoleting packages look for multiple archs per name
        # if you find it look for the packages they obsolete
        # 
        for pkgtup in self.rawobsoletes.keys():
            (name, arch, epoch, ver, rel) = pkgtup
            for (obs_n, flag, (obs_e, obs_v, obs_r)) in self.rawobsoletes[(pkgtup)]:
                if flag in [None, 0]: # unversioned obsolete
                    if pkgdict.has_key((obs_n, None)):
                        for (rpm_a, rpm_e, rpm_v, rpm_r) in pkgdict[(obs_n, None)]:
                            if not obsdict.has_key(pkgtup):
                                obsdict[pkgtup] = []
                            obsdict[pkgtup].append((obs_n, rpm_a, rpm_e, rpm_v, rpm_r))

                else: # versioned obsolete
                    if pkgdict.has_key((obs_n, None)):
                        for (rpm_a, rpm_e, rpm_v, rpm_r) in pkgdict[(obs_n, None)]:
                            if rpmUtils.miscutils.rangeCheck((obs_n, flag, (obs_e, \
                                                        obs_v, obs_r)), (obs_n,\
                                                        rpm_a, rpm_e, rpm_v, rpm_r)):
                                # make sure the obsoleting pkg is not already installed
                                if not obsdict.has_key(pkgtup):
                                    obsdict[pkgtup] = []
                                obsdict[pkgtup].append((obs_n, rpm_a, rpm_e, rpm_v, rpm_r))
        
        obslist = obsdict.keys()
        if newest:
            obslist = self._reduceListNewestByNameArch(obslist)

        returndict = {}
        for new in obslist:
            for old in obsdict[new]:
                if not returndict.has_key(old):
                    returndict[old] = []
                returndict[old].append(new)
        
        return returndict
        
    def doObsoletes(self):
        """figures out what things available obsolete things installed, returns
           them in a dict attribute of the class."""

        obsdict = {} # obseleting package -> [obsoleted package]
        # this needs to keep arch in mind
        # if foo.i386 obsoletes bar
        # it needs to obsoletes bar.i386 preferentially, not bar.x86_64
        # if there is only one bar and only one foo then obsolete it, but try to
        # match the arch.
        
        # look through all the obsoleting packages look for multiple archs per name
        # if you find it look for the packages they obsolete
        # 
        for pkgtup in self.rawobsoletes.keys():
            (name, arch, epoch, ver, rel) = pkgtup
            for (obs_n, flag, (obs_e, obs_v, obs_r)) in self.rawobsoletes[(pkgtup)]:
                if flag in [None, 0]: # unversioned obsolete
                    if self.installdict.has_key((obs_n, None)):
                        for (rpm_a, rpm_e, rpm_v, rpm_r) in self.installdict[(obs_n, None)]:
                            # make sure the obsoleting pkg is not already installed
                            willInstall = 1
                            if self.installdict.has_key((name, None)):
                                for (ins_a, ins_e, ins_v, ins_r) in self.installdict[(name, None)]:
                                    pkgver = (epoch, ver, rel)
                                    installedver = (ins_e, ins_v, ins_r)
                                    if self.returnNewest((pkgver, installedver)) == installedver:
                                        willInstall = 0
                                        break
                            if willInstall:
                                if not obsdict.has_key(pkgtup):
                                    obsdict[pkgtup] = []
                                obsdict[pkgtup].append((obs_n, rpm_a, rpm_e, rpm_v, rpm_r))

                else: # versioned obsolete
                    if self.installdict.has_key((obs_n, None)):
                        for (rpm_a, rpm_e, rpm_v, rpm_r) in self.installdict[(obs_n, None)]:
                            if rpmUtils.miscutils.rangeCheck((obs_n, flag, (obs_e, \
                                                        obs_v, obs_r)), (obs_n,\
                                                        rpm_a, rpm_e, rpm_v, rpm_r)):
                                # make sure the obsoleting pkg is not already installed
                                willInstall = 1
                                if self.installdict.has_key((name, None)):
                                    for (ins_a, ins_e, ins_v, ins_r) in self.installdict[(name, None)]:
                                        pkgver = (epoch, ver, rel)
                                        installedver = (ins_e, ins_v, ins_r)
                                        if self.returnNewest((pkgver, installedver)) == installedver:
                                            willInstall = 0
                                            break
                                if willInstall:
                                    if not obsdict.has_key(pkgtup):
                                        obsdict[pkgtup] = []
                                    obsdict[pkgtup].append((obs_n, rpm_a, rpm_e, rpm_v, rpm_r))
           
        self.obsoletes = obsdict
        self.makeObsoletedDict()

    def makeObsoletedDict(self):
        """creates a dict of obsoleted packages -> [obsoleting package], this
           is to make it easier to look up what package obsoletes what item in 
           the rpmdb"""
        self.obsoleted_dict = {}
        for new in self.obsoletes.keys():
            for old in self.obsoletes[new]:
                if not self.obsoleted_dict.has_key(old):
                    self.obsoleted_dict[old] = []
                self.obsoleted_dict[old].append(new)
    
    def doUpdates(self):
        """check for key lists as populated then commit acts of evil to
           determine what is updated and/or obsoleted, populate self.updatesdict
        """
        
        
        # best bet is to chew through the pkgs and throw out the new ones early
        # then deal with the ones where there are a single pkg installed and a 
        # single pkg available
        # then deal with the multiples

        # we should take the whole list as a 'newlist' and remove those entries
        # which are clearly:
        #   1. updates 
        #   2. identical to the ones in ourdb
        #   3. not in our archdict at all
        
        simpleupdate = []
        complexupdate = []
        
        updatedict = {} # (old n, a, e, v, r) : [(new n, a, e, v, r)]
                        # make the new ones a list b/c while we _shouldn't_
                        # have multiple updaters, we might and well, it needs
                        # to be solved one way or the other <sigh>
        newpkgs = []
        newpkgs = self.availdict
        
        archlist = rpmUtils.arch.getArchList(self.myarch)
                
        for (n, a) in newpkgs.keys():
            # remove stuff not in our archdict
            # high log here
            if a is None:
                for (arch, e,v,r) in newpkgs[(n, a)]:
                    if arch not in archlist:
                        newpkgs[(n, a)].remove((arch, e,v,r))
                continue
                
            if a not in archlist:
                # high log here
                del newpkgs[(n, a)]
                continue

        # remove the older stuff - if we're doing an update we only want the
        # newest evrs                
        for (n, a) in newpkgs.keys():
            if a is None:
                continue

            (new_e,new_v,new_r) = self.returnNewest(newpkgs[(n, a)])
            for (e, v, r) in newpkgs[(n, a)]:
                if (new_e, new_v, new_r) != (e, v, r):
                    newpkgs[(n, a)].remove((e, v, r))

                
        for (n, a) in newpkgs.keys():
            if a is None: # the None archs are only for lookups
                continue
           
            # simple ones - look for exact matches or older stuff
            if self.installdict.has_key((n, a)):
                for (rpm_e, rpm_v, rpm_r) in self.installdict[(n, a)]:
                    try:
                        (e, v, r) = self.returnNewest(newpkgs[(n,a)])
                    except rpmUtils.RpmUtilsError:
                        continue
                    else:
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc <= 0:
                            try:
                                newpkgs[(n, a)].remove((e, v, r))
                            except ValueError:
                               pass

        # get rid of all the empty dict entries:
        for nakey in newpkgs.keys():
            if len(newpkgs[nakey]) == 0:
                del newpkgs[nakey]


        # ok at this point our newpkgs list should be thinned, we should have only
        # the newest e,v,r's and only archs we can actually use
        for (n, a) in newpkgs.keys():
            if a is None: # the None archs are only for lookups
                continue
    
            if self.installdict.has_key((n, None)):
                installarchs = []
                availarchs = []
                for (a, e, v ,r) in newpkgs[(n, None)]:
                    availarchs.append(a)
                for (a, e, v, r) in self.installdict[(n, None)]:
                    installarchs.append(a)

                if len(availarchs) > 1 or len(installarchs) > 1:
                    self.debugprint('putting %s in complex update' % n)
                    complexupdate.append(n)
                else:
                    #log(4, 'putting %s in simple update list' % name)
                    self.debugprint('putting %s in simple update' % n)
                    simpleupdate.append((n, a))

        # we have our lists to work with now
    
        # simple cases
        for (n, a) in simpleupdate:
            # try to be as precise as possible
            if n in self.exactarchlist:
                if self.installdict.has_key((n, a)):
                    (rpm_e, rpm_v, rpm_r) = self.returnNewest(self.installdict[(n, a)])
                    if newpkgs.has_key((n,a)):
                        (e, v, r) = self.returnNewest(newpkgs[(n, a)])
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if not updatedict.has_key((n, a, rpm_e, rpm_v, rpm_r)):
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
    
            else:
                # we could only have 1 arch in our rpmdb and 1 arch of pkg 
                # available - so we shouldn't have to worry about the lists, here
                # we just need to find the arch of the installed pkg so we can 
                # check it's (e, v, r)
                (rpm_a, rpm_e, rpm_v, rpm_r) = self.installdict[(n, None)][0]
                if newpkgs.has_key((n, None)):
                    for (a, e, v, r) in newpkgs[(n, None)]:
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if not updatedict.has_key((n, rpm_a, rpm_e, rpm_v, rpm_r)):
                                updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))


        # complex cases

        # we're multilib/biarch
        # we need to check the name.arch in two different trees
        # one for the multiarch itself and one for the compat arch
        # ie: x86_64 and athlon(i686-i386) - we don't want to descend
        # x86_64->i686 
        archlists = []
        if rpmUtils.arch.isMultiLibArch(arch=self.myarch):
            if rpmUtils.arch.multilibArches.has_key(self.myarch):
                biarches = [self.myarch]
            else:
                biarches = [self.myarch, rpmUtils.arch.arches[self.myarch]]

            multicompat = rpmUtils.arch.getMultiArchInfo(self.myarch)[0]
            multiarchlist = rpmUtils.arch.getArchList(multicompat)
            archlists = [ biarches, multiarchlist ]
        else:
            archlists = [ archlist ]
            
        for n in complexupdate:
            for thisarchlist in archlists:
                # we need to get the highest version and the archs that have it
                # of the installed pkgs            
                tmplist = []
                for (a, e, v, r) in self.installdict[(n, None)]:
                    tmplist.append((n, a, e, v, r))

                highestinstalledpkgs = self.returnHighestVerFromAllArchsByName(n,
                                         thisarchlist, tmplist)
                                         
                
                tmplist = []
                for (a, e, v, r) in newpkgs[(n, None)]:
                    tmplist.append((n, a, e, v, r))                        
                
                highestavailablepkgs = self.returnHighestVerFromAllArchsByName(n,
                                         thisarchlist, tmplist)

                hapdict = self.makeNADict(highestavailablepkgs, 0)
                hipdict = self.makeNADict(highestinstalledpkgs, 0)

                # now we have the two sets of pkgs
                if n in self.exactarchlist:
                    for (n, a) in hipdict:
                        if hapdict.has_key((n, a)):
                            self.debugprint('processing %s.%s' % (n, a))
                            # we've got a match - get our versions and compare
                            (rpm_e, rpm_v, rpm_r) = hipdict[(n, a)][0] # only ever going to be first one
                            (e, v, r) = hapdict[(n, a)][0] # there can be only one
                            rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                            if rc > 0:
                                # this is definitely an update - put it in the dict
                                if not updatedict.has_key((n, a, rpm_e, rpm_v, rpm_r)):
                                    updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                else:
                    self.debugprint('processing %s' % n)
                    # this is where we have to have an arch contest if there
                    # is more than one arch updating with the highest ver
                    instarchs = []
                    availarchs = []
                    for (n,a) in hipdict.keys():
                        instarchs.append(a)
                    for (n,a) in hapdict.keys():
                        availarchs.append(a)
                    
                    rpm_a = rpmUtils.arch.getBestArchFromList(instarchs, myarch=self.myarch)
                    a = rpmUtils.arch.getBestArchFromList(availarchs, myarch=self.myarch)

                    if rpm_a is None or a is None:
                        continue
                        
                    (rpm_e, rpm_v, rpm_r) = hipdict[(n, rpm_a)][0] # there can be just one
                    (e, v, r) = hapdict[(n, a)][0] # just one, I'm sure, I swear!

                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))

                    if rc > 0:
                        # this is definitely an update - put it in the dict
                        if not updatedict.has_key((n, rpm_a, rpm_e, rpm_v, rpm_r)):
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                        updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                   
                   
        self.updatesdict = updatedict                    
        self.makeUpdatingDict()
        
    def makeUpdatingDict(self):
        """creates a dict of available packages -> [installed package], this
           is to make it easier to look up what package  will be updating what
           in the rpmdb"""
        self.updating_dict = {}
        for old in self.updatesdict.keys():
            for new in self.updatesdict[old]:
                if not self.updating_dict.has_key(new):
                    self.updating_dict[new] = []
                self.updating_dict[new].append(old)

    def reduceListByNameArch(self, pkglist, name=None, arch=None):
        """returns a set of pkg naevr tuples reduced based on name or arch"""
        returnlist = []
       
        if name or arch:
            for (n, a, e, v, r) in pkglist:
                if name:
                    if name == n:
                        returnlist.append((n, a, e, v, r))
                        continue
                if arch:
                    if arch == a:
                        returnlist.append((n, a, e, v, r))
                        continue
        else:
            returnlist = pkglist

        return returnlist
        
        
    def getUpdatesTuples(self, name=None, arch=None):
        """returns updates for packages in a list of tuples of:
          (updating naevr, installed naevr)"""
        returnlist = []
        for oldtup in self.updatesdict.keys():
            (old_n, old_a, old_e, old_v, old_r) = oldtup
            for newtup in self.updatesdict[oldtup]:
                returnlist.append((newtup, oldtup))
        
        tmplist = []
        if name:
            for ((n, a, e, v, r), oldtup) in returnlist:
                if name != n:
                    tmplist.append(((n, a, e, v, r), oldtup))
        if arch:
            for ((n, a, e, v, r), oldtup) in returnlist:
                if arch != a:
                    tmplist.append(((n, a, e, v, r), oldtup))

        for item in tmplist:
            try:
                returnlist.remove(item)
            except ValueError:
                pass
                
        return returnlist            

    def getUpdatesList(self, name=None, arch=None):
        """returns updating packages in a list of (naevr) tuples"""
        returnlist = []

        for oldtup in self.updatesdict.keys():
            for newtup in self.updatesdict[oldtup]:
                returnlist.append(newtup)
        
        returnlist = self.reduceListByNameArch(returnlist, name, arch)
        
        return returnlist
                
    def getObsoletesTuples(self, newest=0, name=None, arch=None):
        """returns obsoletes for packages in a list of tuples of:
           (obsoleting naevr, installed naevr). You can specify name and/or
           arch of the installed package to narrow the results.
           You can also specify newest=1 to get the set of newest pkgs (name, arch)
           sorted, that obsolete something"""
           
        tmplist = []
        obslist = self.obsoletes.keys()
        if newest:
            obslist = self._reduceListNewestByNameArch(obslist)
            
        for obstup in obslist:
            for rpmtup in self.obsoletes[obstup]:
                tmplist.append((obstup, rpmtup))
        
        returnlist = []
        if name or arch:
            for (obstup, (n, a, e, v, r)) in tmplist:
                if name:
                    if name == n:
                        returnlist.append((obstup, (n, a, e, v, r)))
                        continue
                if arch:
                    if arch == a:
                        returnlist.append((obstup, (n, a, e, v, r)))
                        continue
        else:
            returnlist = tmplist

        return returnlist
                        
           
           
    def getObsoletesList(self, newest=0, name=None, arch=None):
        """returns obsoleting packages in a list of naevr tuples of just the
           packages that obsolete something that is installed. You can specify
           name and/or arch of the obsoleting packaging to narrow the results.
           You can also specify newest=1 to get the set of newest pkgs (name, arch)
           sorted, that obsolete something"""
           
        tmplist = self.obsoletes.keys()
        if newest:
            tmplist = self._reduceListNewestByNameArch(tmplist)

        returnlist = self.reduceListByNameArch(tmplist, name, arch)
        
        return returnlist
    
    def getObsoletedList(self, newest=0, name=None):
        """returns a list of pkgtuples obsoleting the package in name"""
        returnlist = []
        for new in self.obsoletes.keys():
            for obstup in self.obsoletes[new]:
                (n, a, e, v, r) = obstup
                if n == name:
                    returnlist.append(new)
                    continue
        return returnlist


        
    def getOthersList(self, name=None, arch=None):
        """returns a naevr tuple of the packages that are neither installed
           nor an update - this may include something that obsoletes an installed
           package"""
        updates = {}
        inst = {}
        tmplist = []
        
        for pkgtup in self.getUpdatesList():
            updates[pkgtup] = 1
            
        for pkgtup in self.installed:
            inst[pkgtup] = 1
            
        for pkgtup in self.available:
            if not updates.has_key(pkgtup) and not inst.has_key(pkgtup):
                tmplist.append(pkgtup)

        returnlist = self.reduceListByNameArch(tmplist, name, arch)
        
        return returnlist
         


    def _reduceListNewestByNameArch(self, tuplelist):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not 
           compared to each other for highest version only foo.i386 and 
           foo.i386 will be compared"""
        highdict = {}
        for pkgtup in tuplelist:
            (n, a, e, v, r) = pkgtup
            if not highdict.has_key((n, a)):
                highdict[(n, a)] = pkgtup
            else:
                pkgtup2 = highdict[(n, a)]
                (n2, a2, e2, v2, r2) = pkgtup2
                rc = rpmUtils.miscutils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[(n, a)] = pkgtup
        
        return highdict.values()

            
#    def getProblems(self):
#        """return list of problems:
#           - Packages that are both obsoleted and updated.
#           - Packages that have multiple obsoletes.
#           - Packages that _still_ have multiple updates
#        """

             
