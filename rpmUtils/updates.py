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

import rpmUtils
import rpmUtils.miscutils
import rpmUtils.arch

def _vertup_cmp(tup1, tup2):
    return rpmUtils.miscutils.compareEVR(tup1, tup2)
class Updates:
    """
    This class computes and keeps track of updates and obsoletes.
    initialize, add installed packages, add available packages (both as
    unique lists of name, arch, ver, rel, epoch tuples), add an optional dict
    of obsoleting packages with obsoletes and what they obsolete ie::
        foo, i386, 0, 1.1, 1: bar >= 1.1.
    """

    def __init__(self, instlist, availlist):

        self.installed = instlist # list of installed pkgs (n, a, e, v, r)
        self.available = availlist # list of available pkgs (n, a, e, v, r)

        self.rawobsoletes = {} # dict of obsoleting package->[what it obsoletes]
        self._obsoletes_by_name = None
        self.obsoleted_dict = {}  # obsoleted pkgtup -> [ obsoleting pkgtups ]
        self.obsoleting_dict = {} # obsoleting pkgtup -> [ obsoleted pkgtups ]

        self.exactarch = 1 # don't change archs by default
        self.exactarchlist = set(['kernel', 'kernel-smp', 'glibc',
                                  'kernel-hugemem',
                                  'kernel-enterprise', 'kernel-bigmem',
                                  'kernel-BOOT'])
                              
        self.myarch = rpmUtils.arch.canonArch # set this if you want to
                                              # test on some other arch
                                              # otherwise leave it alone
        self._is_multilib = rpmUtils.arch.isMultiLibArch(self.myarch)
        
        self._archlist = rpmUtils.arch.getArchList(self.myarch)

        self._multilib_compat_arches = rpmUtils.arch.getMultiArchInfo(self.myarch)

        # make some dicts from installed and available
        self.installdict = self.makeNADict(self.installed, 1)
        self.availdict = self.makeNADict(self.available, 0, # Done in doUpdate
                                         filter=self.installdict)

        # holder for our updates dict
        self.updatesdict = {}
        self.updating_dict = {}
        #debug, ignore me
        self.debug = 0
        self.obsoletes = {}

    def _delFromDict(self, dict_, keys, value):
        for key in keys:
            if key not in dict_:
                continue
            dict_[key] = filter(value.__ne__, dict_[key])
            if not dict_[key]:
                del dict_[key]

    def _delFromNADict(self, dict_, pkgtup):
        (n, a, e, v, r) = pkgtup
        for aa in (a, None):
            if (n, aa) in dict_:
                dict_[(n, aa)] = filter((e,v,r).__ne__, dict_[(n, aa)])
                if not dict_[(n, aa)]:
                    del dict_[(n, aa)]

    def delPackage(self, pkgtup):
        """remove available pkgtup that is no longer available"""
        if pkgtup not in self.available:
            return
        self.available.remove(pkgtup)
        self._delFromNADict(self.availdict, pkgtup)

        self._delFromDict(self.updating_dict, self.updatesdict.get(pkgtup, []), pkgtup)
        self._delFromDict(self.updatesdict, self.updating_dict.get(pkgtup, []), pkgtup)

        if pkgtup in self.rawobsoletes:
            if self._obsoletes_by_name:
                for name, flag, version in self.rawobsoletes[pkgtup]:
                    self._delFromDict(self._obsoletes_by_name, [name], (flag, version, pkgtup))
                del self.rawobsoletes[pkgtup]

        self._delFromDict(self.obsoleted_dict, self.obsoleting_dict.get(pkgtup, []), pkgtup)
        self._delFromDict(self.obsoleting_dict, self.obsoleted_dict.get(pkgtup, []), pkgtup)

    def debugprint(self, msg):
        if self.debug:
            print msg

    def makeNADict(self, pkglist, Nonelists, filter=None):
        """return lists of (e,v,r) tuples as value of a dict keyed on (n, a)
            optionally will return a (n, None) entry with all the a for that
            n in tuples of (a,e,v,r)"""
            
        returndict = {}
        for (n, a, e, v, r) in pkglist:
            if filter and (n, None) not in filter:
                continue
            if (n, a) not in returndict:
                returndict[(n, a)] = []
            if (e,v,r) in returndict[(n, a)]:
                continue
            returndict[(n, a)].append((e,v,r))

            if Nonelists:
                if (n, None) not in returndict:
                    returndict[(n, None)] = []
                if (a,e,v,r) in returndict[(n, None)]:
                    continue
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
        returnlist = []
        high_vertup = None
        for pkgtup in pkglist:
            (n, a, e, v, r) = pkgtup
            # FIXME: returnlist used to _possibly_ contain things not in
            #        archlist ... was that desired?
            if name == n and a in archlist:
                vertup = (e, v, r)
                if (high_vertup is None or
                    (_vertup_cmp(high_vertup, vertup) < 0)):
                    high_vertup = vertup
                    returnlist = []
                if vertup == high_vertup:
                    returnlist.append(pkgtup)

        return returnlist
           
    def condenseUpdates(self):
        """remove any accidental duplicates in updates"""
        
        for tup in self.updatesdict:
            if len(self.updatesdict[tup]) > 1:
                mylist = self.updatesdict[tup]
                self.updatesdict[tup] = rpmUtils.miscutils.unique(mylist)
    
    
    def checkForObsolete(self, pkglist, newest=1):
        """accept a list of packages to check to see if anything obsoletes them
           return an obsoleted_dict in the format of makeObsoletedDict"""
        if self._obsoletes_by_name is None:
            self._obsoletes_by_name = {}
            for pkgtup, obsoletes in self.rawobsoletes.iteritems():
                for name, flag, version in obsoletes:
                    self._obsoletes_by_name.setdefault(name, []).append(
                        (flag, version, pkgtup) )

        obsdict = {} # obseleting package -> [obsoleted package]

        for pkgtup in pkglist:
            name = pkgtup[0]
            for obs_flag, obs_version, obsoleting in self._obsoletes_by_name.get(name, []):
                if obs_flag in [None, 0] and name == obsoleting[0]: continue
                if rpmUtils.miscutils.rangeCheck( (name, obs_flag, obs_version), pkgtup):
                    obsdict.setdefault(obsoleting, []).append(pkgtup)

        if not obsdict:
            return {}

        obslist = obsdict.keys()
        if newest:
            obslist = self._reduceListNewestByNameArch(obslist)

        returndict = {}
        for new in obslist:
            for old in obsdict[new]:
                if old not in returndict:
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
        obs_arches = {}
        for (n, a, e, v, r) in self.rawobsoletes:
            if n not in obs_arches:
                obs_arches[n] = []
            obs_arches[n].append(a)

        for pkgtup in self.rawobsoletes:
            (name, arch, epoch, ver, rel) = pkgtup
            for (obs_n, flag, (obs_e, obs_v, obs_r)) in self.rawobsoletes[(pkgtup)]:
                if (obs_n, None) in self.installdict:
                    for (rpm_a, rpm_e, rpm_v, rpm_r) in self.installdict[(obs_n, None)]:
                        if flag in [None, 0] or \
                                rpmUtils.miscutils.rangeCheck((obs_n, flag, (obs_e, obs_v, obs_r)),
                                                              (obs_n, rpm_a, rpm_e, rpm_v, rpm_r)):
                            # make sure the obsoleting pkg is not already installed
                            willInstall = 1
                            if (name, None) in self.installdict:
                                for (ins_a, ins_e, ins_v, ins_r) in self.installdict[(name, None)]:
                                    pkgver = (epoch, ver, rel)
                                    installedver = (ins_e, ins_v, ins_r)
                                    if self.returnNewest((pkgver, installedver)) == installedver:
                                        willInstall = 0
                                        break
                            if rpm_a != arch and rpm_a in obs_arches[name]:
                                willInstall = 0
                            if willInstall:
                                if pkgtup not in obsdict:
                                    obsdict[pkgtup] = []
                                obsdict[pkgtup].append((obs_n, rpm_a, rpm_e, rpm_v, rpm_r))
        self.obsoletes = obsdict
        self.makeObsoletedDict()

    def makeObsoletedDict(self):
        """creates a dict of obsoleted packages -> [obsoleting package], this
           is to make it easier to look up what package obsoletes what item in 
           the rpmdb"""
        self.obsoleted_dict = {}
        for new in self.obsoletes:
            for old in self.obsoletes[new]:
                if old not in self.obsoleted_dict:
                    self.obsoleted_dict[old] = []
                self.obsoleted_dict[old].append(new)
        self.obsoleting_dict = {}
        for obsoleted, obsoletings in self.obsoleted_dict.iteritems():
            for obsoleting in obsoletings:
                self.obsoleting_dict.setdefault(obsoleting, []).append(obsoleted)
    
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
        newpkgs = self.availdict
        
        archlist = self._archlist 
        for (n, a) in newpkgs.keys():
            if a not in archlist:
                # high log here
                del newpkgs[(n, a)]
                continue

        # remove the older stuff - if we're doing an update we only want the
        # newest evrs                
        for (n, a) in newpkgs:
            (new_e,new_v,new_r) = self.returnNewest(newpkgs[(n, a)])
            for (e, v, r) in newpkgs[(n, a)][:]:
                if (new_e, new_v, new_r) != (e, v, r):
                    newpkgs[(n, a)].remove((e, v, r))

        for (n, a) in newpkgs:
            # simple ones - look for exact matches or older stuff
            if (n, a) in self.installdict:
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

        # Now we add the (n, None) entries back...
        for na in newpkgs.keys():
            all_arches = map(lambda x: (na[1], x[0], x[1], x[2]), newpkgs[na])
            newpkgs.setdefault((na[0], None), []).extend(all_arches)

        # get rid of all the empty dict entries:
        for nakey in newpkgs.keys():
            if len(newpkgs[nakey]) == 0:
                del newpkgs[nakey]


        # ok at this point our newpkgs list should be thinned, we should have only
        # the newest e,v,r's and only archs we can actually use
        for (n, a) in newpkgs:
            if a is None: # the None archs are only for lookups
                continue
    
            if (n, None) in self.installdict:
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
                if (n, a) in self.installdict:
                    (rpm_e, rpm_v, rpm_r) = self.returnNewest(self.installdict[(n, a)])
                    if (n, a) in newpkgs:
                        (e, v, r) = self.returnNewest(newpkgs[(n, a)])
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if (n, a, rpm_e, rpm_v, rpm_r) not in updatedict:
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
    
            else:
                # we could only have 1 arch in our rpmdb and 1 arch of pkg 
                # available - so we shouldn't have to worry about the lists, here
                # we just need to find the arch of the installed pkg so we can 
                # check it's (e, v, r)
                (rpm_a, rpm_e, rpm_v, rpm_r) = self.installdict[(n, None)][0]
                if (n, None) in newpkgs:
                    for (a, e, v, r) in newpkgs[(n, None)]:
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if (n, rpm_a, rpm_e, rpm_v, rpm_r) not in updatedict:
                                updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))


        # complex cases

        # we're multilib/biarch
        # we need to check the name.arch in two different trees
        # one for the multiarch itself and one for the compat arch
        # ie: x86_64 and athlon(i686-i386) - we don't want to descend
        # x86_64->i686 
        # however, we do want to descend x86_64->noarch, sadly.
        
        archlists = []
        if self._is_multilib:
            if self.myarch in rpmUtils.arch.multilibArches:
                biarches = [self.myarch]
            else:
                biarches = [self.myarch, rpmUtils.arch.arches[self.myarch]]
            biarches.append('noarch')
            
            multicompat = self._multilib_compat_arches[0]
            multiarchlist = rpmUtils.arch.getArchList(multicompat)
            archlists = [ set(biarches), set(multiarchlist) ]
            # archlists = [ biarches, multiarchlist ]
        else:
            archlists = [ set(archlist) ]
            # archlists = [ archlist ]
            
        for n in complexupdate:
            for thisarchlist in archlists:
                # we need to get the highest version and the archs that have it
                # of the installed pkgs            
                tmplist = []
                for (a, e, v, r) in self.installdict[(n, None)]:
                    tmplist.append((n, a, e, v, r))

                highestinstalledpkgs = self.returnHighestVerFromAllArchsByName(n,
                                         thisarchlist, tmplist)
                hipdict = self.makeNADict(highestinstalledpkgs, 0)
                                         
                
                if n in self.exactarchlist:
                    tmplist = []
                    for (a, e, v, r) in newpkgs[(n, None)]:
                        tmplist.append((n, a, e, v, r))
                    highestavailablepkgs = self.returnHighestVerFromAllArchsByName(n,
                                             thisarchlist, tmplist)

                    hapdict = self.makeNADict(highestavailablepkgs, 0)

                    for (n, a) in hipdict:
                        if (n, a) in hapdict:
                            self.debugprint('processing %s.%s' % (n, a))
                            # we've got a match - get our versions and compare
                            (rpm_e, rpm_v, rpm_r) = hipdict[(n, a)][0] # only ever going to be first one
                            (e, v, r) = hapdict[(n, a)][0] # there can be only one
                            rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                            if rc > 0:
                                # this is definitely an update - put it in the dict
                                if (n, a, rpm_e, rpm_v, rpm_r) not in updatedict:
                                    updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                else:
                    self.debugprint('processing %s' % n)
                    # this is where we have to have an arch contest if there
                    # is more than one arch updating with the highest ver
                    instarchs = []
                    for (n,a) in hipdict:
                        instarchs.append(a)
                    
                    rpm_a = rpmUtils.arch.getBestArchFromList(instarchs, myarch=self.myarch)
                    if rpm_a is None:
                        continue

                    tmplist = []
                    for (a, e, v, r) in newpkgs[(n, None)]:
                        tmplist.append((n, a, e, v, r))
                    highestavailablepkgs = self.returnHighestVerFromAllArchsByName(n,
                                             thisarchlist, tmplist)

                    hapdict = self.makeNADict(highestavailablepkgs, 0)
                    availarchs = []
                    for (n,a) in hapdict:
                        availarchs.append(a)
                    a = rpmUtils.arch.getBestArchFromList(availarchs, myarch=self.myarch)
                    if a is None:
                        continue
                        
                    (rpm_e, rpm_v, rpm_r) = hipdict[(n, rpm_a)][0] # there can be just one
                    (e, v, r) = hapdict[(n, a)][0] # just one, I'm sure, I swear!
                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                    if rc > 0:
                        # this is definitely an update - put it in the dict
                        if (n, rpm_a, rpm_e, rpm_v, rpm_r) not in updatedict:
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                        updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                   
        self.updatesdict = updatedict                    
        self.makeUpdatingDict()
        
    def makeUpdatingDict(self):
        """creates a dict of available packages -> [installed package], this
           is to make it easier to look up what package  will be updating what
           in the rpmdb"""
        self.updating_dict = {}
        for old in self.updatesdict:
            for new in self.updatesdict[old]:
                if new not in self.updating_dict:
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
        for oldtup in self.updatesdict:
            for newtup in self.updatesdict[oldtup]:
                returnlist.append((newtup, oldtup))
        
        # self.reduceListByNameArch() for double tuples
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

        for oldtup in self.updatesdict:
            for newtup in self.updatesdict[oldtup]:
                returnlist.append(newtup)
        
        returnlist = self.reduceListByNameArch(returnlist, name, arch)
        
        return returnlist
                
    # NOTE: This returns obsoleters and obsoletees, but narrows based on
    # _obsoletees_ (unlike getObsoletesList). Look at getObsoletersTuples
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
        
        # self.reduceListByNameArch() for double tuples
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
                        
    # NOTE: This returns obsoleters and obsoletees, but narrows based on
    # _obsoleters_ (like getObsoletesList).
    def getObsoletersTuples(self, newest=0, name=None, arch=None):
        """returns obsoletes for packages in a list of tuples of:
           (obsoleting naevr, installed naevr). You can specify name and/or
           arch of the obsoleting package to narrow the results.
           You can also specify newest=1 to get the set of newest pkgs (name, arch)
           sorted, that obsolete something"""
           
        tmplist = []
        obslist = self.obsoletes.keys()
        if newest:
            obslist = self._reduceListNewestByNameArch(obslist)

        for obstup in obslist:
            for rpmtup in self.obsoletes[obstup]:
                tmplist.append((obstup, rpmtup))

        # self.reduceListByNameArch() for double tuples
        returnlist = []
        if name or arch:
            for ((n, a, e, v, r), insttup) in tmplist:
                if name:
                    if name == n:
                        returnlist.append(((n, a, e, v, r), insttup))
                        continue
                if arch:
                    if arch == a:
                        returnlist.append(((n, a, e, v, r), insttup))
                        continue
        else:
            returnlist = tmplist

        return returnlist
           
    # NOTE: This returns _obsoleters_, and narrows based on that (unlike
    # getObsoletesTuples, but like getObsoletersTuples)
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
        for new in self.obsoletes:
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
            if pkgtup not in updates and pkgtup not in inst:
                tmplist.append(pkgtup)

        returnlist = self.reduceListByNameArch(tmplist, name, arch)
        
        return returnlist
         


    def _reduceListNewestByNameArch(self, tuplelist):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not 
           compared to each other for highest version only foo.i386 and 
           foo.i386 will be compared"""
        highdict = {}
        done = False
        for pkgtup in tuplelist:
            (n, a, e, v, r) = pkgtup
            if (n, a) not in highdict:
                highdict[(n, a)] = pkgtup
            else:
                pkgtup2 = highdict[(n, a)]
                done = True
                (n2, a2, e2, v2, r2) = pkgtup2
                rc = rpmUtils.miscutils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[(n, a)] = pkgtup
        
        if not done:
            return tuplelist

        return highdict.values()

            
#    def getProblems(self):
#        """return list of problems:
#           - Packages that are both obsoleted and updated.
#           - Packages that have multiple obsoletes.
#           - Packages that _still_ have multiple updates
#        """

             
