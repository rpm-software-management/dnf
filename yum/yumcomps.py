#!/usr/bin/python

import rpm
import comps
import sys
import rpmUtils
from libxml2 import parserError

# goals
# be able to list which groups a user has installed based on whether or
# not mandatory pkgs are installed and whether all the metapkgs are installed
# (consider making metapkgs groups with settings in this model)
# so groups have end up being default, optional or mandatory
# - all groups (as listed in the xml file are default only)
# so installgroup X installs all the default+mandatory pkgs and any group

# determine if groupreqs are included on install

# is installed? - group reqs not consulted - metapkgs and pkgs in mandatory 
# install - groupreqs installed too - metapkgs in default or better 
#           and pkgs in default or better
# update - if pkg in group installed (any class of pkg) check for update, 
#          all mandatory pkgs and metapkgs will be updated/installed if possible
#           ???? Ask - should update recurse the pkg group list so you could run
#           yum groupupdate "Workstation Common"
# erase - only pkgs in group - not subgroups nor metapkgs
# 

# gist of operation of this class:
# create the class
# add  comps.xml type files
# compile the groups
# then you can perform the functions on the groups

# which groups are around.
# maybe parse the files, populate the fields as much as possible then sweep
# through and calculate things after all the .xml files have been added
# need to deal with groupname vs groupid

class Groups_Info:
    def __init__(self, overwrite_groups = 0):
        self.overwrite_groups = overwrite_groups
        self.group_installed = {}
        self.sub_groups = {}
        self.visible_groups = []
        self.group_by_id = {}
        self.group_by_name = {}
        self.optional_pkgs = {}
        self.mandatory_pkgs = {}
        self.default_pkgs = {}
        self.grouplist = []
        self.optional_metapkgs = {}
        self.default_metapkgs = {}
        # mandatory_metapkgs are a figment of our imagination but I'm leaving this
        # as they might be used later
        self.mandatory_metapkgs = {}
        self.installed_pkgs = {}
        self.pkgs_per_group = {}
        self.compscount = 0
        # get our list of installed stuff real quickly
        self._get_installed()
        
    def add(self, filename):
        """This method takes a filename and populates the above dicts"""
        try:
            compsobj = comps.Comps(filename)
        except comps.CompsException, e:
            print 'Damaged xml file error:\n %s' % e
            return
        except parserError, e:
            print 'Damaged or Empty xml file error: \n %s' % e
            return
        self.compscount = self.compscount + 1
        groupsobj = compsobj.groups
        groups = groupsobj.keys()
        
        # quick run through - create the groupid and groupname lookup
        # look out for groupmerging vs overwrite here
        for groupname in groups:
            id = groupsobj[groupname].id
            self.group_by_id[id] = groupname
            self.group_by_name[groupname] = id
            
        # should populate for all groups but only act on uservisible groups only
        
        for groupname in groups:
            thisgroup = groupsobj[groupname]
            
            if thisgroup.user_visible:
                self.visible_groups.append(groupname)
            
            # make all the key entries if we don't already have them
            if groupname not in self.grouplist:
                self.grouplist.append(groupname)
                self.group_installed[groupname]=0
                self.mandatory_pkgs[groupname] = []
                self.sub_groups[groupname] = []
                self.optional_pkgs[groupname] = []
                self.default_pkgs[groupname] = []
                self.mandatory_metapkgs[groupname] = []
                self.default_metapkgs[groupname] = []
                self.optional_metapkgs[groupname] = []
                
            # if we're overwriting groups - kill all the originals
            if self.overwrite_groups:
                self.group_installed[groupname] = 0
                self.mandatory_pkgs[groupname] = []
                self.sub_groups[groupname] = []
                self.optional_pkgs[groupname] = []
                self.default_pkgs[groupname] = []
                self.mandatory_metapkgs[groupname] = []
                self.optional_metapkgs[groupname] = []
                self.default_metapkgs[groupname] = []
                
            packageobj = thisgroup.packages
            pkgs = packageobj.keys()
                            
            for pkg in pkgs:
                (type, name) = packageobj[pkg]
                if type == u'mandatory':
                    self.mandatory_pkgs[groupname].append(name)
                elif type == u'optional':
                    self.optional_pkgs[groupname].append(name)
                elif type == u'default':
                    self.default_pkgs[groupname].append(name)
                else:
                    print '%s not optional, default or mandatory - ignoring' % name
                
            for sub_group_id in thisgroup.groups.keys():
                if sub_group_id in self.sub_groups[groupname]:
                    print 'Duplicate group entry %s in %s' % (sub_group_id, groupname)
                else:
                    self.sub_groups[groupname].append(sub_group_id)
            
            metapkgobj = thisgroup.metapkgs
            for metapkg in metapkgobj.keys():
                (type, metapkgid) = metapkgobj[metapkg]
                if type == u'mandatory':
                    self.mandatory_metapkgs[groupname].append(metapkgid)
                elif type == u'optional':
                    self.optional_metapkgs[groupname].append(metapkgid)
                elif type == u'default':
                    self.default_metapkgs[groupname].append(metapkgid)
                else:
                    print '%s not optional, default or mandatory - ignoring' % metapkgid
                    
        
    def compileGroups(self):
        self._correctGroups()
        self._installedgroups()
        self._pkgs_per_group()
        
    def _correctGroups(self):
        for key in self.sub_groups.keys():
            newlist = []
            for id in self.sub_groups[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(self.group_by_id[id])
                else:
                    print 'Invalid group id %s' % id
            self.sub_groups[key] = newlist
        
        for key in self.mandatory_metapkgs.keys():
            newlist = []
            for id in self.mandatory_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(self.group_by_id[id])
                else:
                    print 'Invalid metapkg id %s' % id
            self.mandatory_metapkgs[key] = newlist
            
        for key in self.default_metapkgs.keys():
            newlist = []
            for id in self.default_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(self.group_by_id[id])
                else:
                    print 'Invalid metapkg id %s' % id
            self.default_metapkgs[key] = newlist

        for key in self.optional_metapkgs.keys():
            newlist = []
            for id in self.optional_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(self.group_by_id[id])
                else:
                    print 'Invalid metapkg id %s' % id
            self.optional_metapkgs[key] = newlist

            
    def _installedgroups(self):
        for groupname in self.grouplist:
            if len(self.mandatory_pkgs[groupname]) > 0:
                groupinstalled = 1
                for reqpkg in self.mandatory_pkgs[groupname]:
                    if not self.installed_pkgs.has_key(reqpkg):
                        groupinstalled = 0
                self.group_installed[groupname]=groupinstalled
            else:
                groupinstalled = 0
                for anypkg in self.optional_pkgs[groupname] + self.default_pkgs[groupname]:
                    if self.installed_pkgs.has_key(anypkg):
                        groupinstalled = 1
                self.group_installed[groupname]=groupinstalled
        # now we need to check metapkgs in the groups and see which are mandatory
        # and make sure they're installed if they are
        # if there is a mandatory metapkg and it's not installed then the
        # group that includes it is not installed
        # again - mandatory_metapkgs are just figments - nothing more
        for groupname in self.grouplist:
            if len(self.mandatory_metapkgs[groupname]) > 0:
                for metapkg in self.mandatory_metapkgs[groupname]:
                    if not self.group_installed[metapkg]:
                        groupinstalled = 0
        
    def _get_installed(self):
        """this should reference rpmUtils and or the nevral for speed
           also it needs to obey the excludes - so probably nevral"""
        mi = ts.dbMatch()
        for hdr in mi:
            self.installed_pkgs[hdr['name']]=1
        
        
    def isGroupInstalled(self, groupname):
        return self.group_installed[groupname]
    
    def groupTree(self, groupname):
        """returns list of all groups, recursively, needed by groupname"""
        grouplist = [groupname] + self.sub_groups[groupname] + \
                    self.mandatory_metapkgs[groupname] + self.default_metapkgs[groupname]
        for subgroup in grouplist:
            for group in self.sub_groups[subgroup] + self.mandatory_metapkgs[subgroup] + self.default_metapkgs[subgroup]:
                if group not in grouplist:
                    grouplist.append(group)
        
        return grouplist
        
    def pkgTree(self, groupname):
        """get all pkgs in mandatory and default for all groups and their required 
           groups and metapkgs etc, recursing"""
        grouplist = self.groupTree(groupname)
        pkglist = []
        for group in grouplist:
            for pkg in self.default_pkgs[group] + self.mandatory_pkgs[group]:
                if pkg not in pkglist:
                    pkglist.append(pkg)
        
        return pkglist
                
    def requiredPkgs(self, groupname):
        """return a list of all required pkgs and pkgs _ONLY_ to install this group
           this is not the same as pkgTree b/c it only lists packages for the group,
           it does not recurse through other groupreqs"""
        pkglist = []
        for pkg in self.default_pkgs[groupname] + self.mandatory_pkgs[groupname]:
            if pkg not in pkglist:
                pkglist.append(pkg)
                
        return pkglist
        
    def requiredGroups(self, groupname):
        """return a list of required groups for this group. Do not recurse 
        through the groups"""
        grplist = []
        for group in self.sub_groups[groupname] + self.mandatory_metapkgs[groupname] + self.default_metapkgs[groupname]:
            if group not in grplist:
                grplist.append(group)
         
        return grplist
    
    def allPkgs(self, groupname):
        """duh - return list of all pkgs in group"""
        pkglist = self.requiredPkgs(groupname) + self.optional_pkgs[groupname]
        return pkglist
        
    def _pkgs_per_group(self):
        """ populate the pkgs_per_group dict - produces list of pkgs installed 
            for each group"""
        for group in self.group_installed.keys():
            pkglist = self.optional_pkgs[group] + self.default_pkgs[group] + self.mandatory_pkgs[group]
            for pkg in pkglist:
                if self.installed_pkgs.has_key(pkg):
                    if not self.pkgs_per_group.has_key(group):
                        self.pkgs_per_group[group] = []
                    self.pkgs_per_group[group].append(pkg)
                
    def _dumppkgs(self, reqgroup=None):
        """this is soley used to debug stuff"""
        if reqgroup is None:
            groups = self.visible_groups
        elif reqgroup == "all_installed":
            groups = []
            for grp in self.group_installed.keys():
                if self.group_installed[grp] and grp in self.visible_groups:
                    groups.append(grp)
        else:
            groups = [reqgroup]
            
        for group in groups:
            print 'Group: %s' % group
            for item in self.mandatory_pkgs[group]:
                print '   %s *' % item
            for item in self.default_pkgs[group]:
                print '   %s +' % item
            for item in self.optional_pkgs[group]:
                print '   %s' % item
        for group in groups:
            print 'Inst Pkgs: %s' % group
            self.pkgs_per_group[group].sort()
            for pkg in self.pkgs_per_group[group]:
                print '   %s' % pkg
                


def main():
    compsgrpfun = Groups_Info(overwrite_groups)
    compsgrpfun.add('./comps.xml')
    compsgrpfun.add('./othercomps.xml')
    compsgrpfun.compileGroups()
    #compsgrpfun._dumppkgs('all_installed')
    try:
        groups = compsgrpfun.groupTree(sys.argv[1])
        pkgs = compsgrpfun.pkgTree(sys.argv[1])
        print groups
        print pkgs
    except KeyError, e:
        print 'No Group named %s' % sys.argv[1]


if __name__ == '__main__':
    overwrite_groups = 1
    ts = rpm.TransactionSet()
    main()
