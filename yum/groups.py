#!/usr/bin/python

import comps
import sys
from Errors import GroupsError

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
    def __init__(self, pkgtuples, overwrite_groups = 0):
        self.overwrite_groups = overwrite_groups
        self.group_installed = {}
        self.sub_groups = {}
        self.visible_groups = []
        self.group_by_id = {}
        self.id_by_name = {}
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
        self._get_installed(pkgtuples)
        self.debug = 0
        
    def add(self, filename):
        """This method takes a filename and populates the above dicts"""
        try:
            compsobj = comps.Comps(filename)
        except comps.CompsException, e:
            raise GroupsError, 'Damaged XML file:\n %s' % e
        except SyntaxError, e:
            raise GroupsError, 'Damaged or empty XML file:\n %s' % e

        self.compscount = self.compscount + 1
        groupsobj = compsobj.groups
        groups = groupsobj.values()
        
        # quick run through - create the groupid and groupname lookup
        # look out for groupmerging vs overwrite here
        for thisgroup in groups:
            id = thisgroup.id
            self.group_by_id[id] = thisgroup
            self.id_by_name[thisgroup.name] = id
            groupname = thisgroup.name
            
        # should populate for all groups but only act on uservisible groups only
            if thisgroup.user_visible:
                self.visible_groups.append(id)
            
            # make all the key entries if we don't already have them
            if id not in self.grouplist:
                self.grouplist.append(id)
                self.group_installed[id]=0
                self.mandatory_pkgs[id] = []
                self.sub_groups[id] = []
                self.optional_pkgs[id] = []
                self.default_pkgs[id] = []
                self.mandatory_metapkgs[id] = []
                self.default_metapkgs[id] = []
                self.optional_metapkgs[id] = []
                
            # if we're overwriting groups - kill all the originals
            if self.overwrite_groups:
                self.group_installed[id] = 0
                self.mandatory_pkgs[id] = []
                self.sub_groups[id] = []
                self.optional_pkgs[id] = []
                self.default_pkgs[id] = []
                self.mandatory_metapkgs[id] = []
                self.optional_metapkgs[id] = []
                self.default_metapkgs[id] = []
                
            packageobj = thisgroup.packages
            pkgs = packageobj.keys()
                            
            for pkg in pkgs:
                (type, name) = packageobj[pkg]
                if type == u'mandatory':
                    self.mandatory_pkgs[id].append(name)
                elif type == u'optional':
                    self.optional_pkgs[id].append(name)
                elif type == u'default':
                    self.default_pkgs[id].append(name)
                else:
                    self.debugprint('%s not optional, default or mandatory - ignoring' % name)
                
            for sub_group_id in thisgroup.groups.keys():
                if not sub_group_id in self.sub_groups[id]:
                    self.sub_groups[id].append(sub_group_id)
            
            metapkgobj = thisgroup.metapkgs
            for metapkg in metapkgobj.keys():
                (type, metapkgid) = metapkgobj[metapkg]
                if type == u'mandatory':
                    self.mandatory_metapkgs[id].append(metapkgid)
                elif type == u'optional':
                    self.optional_metapkgs[id].append(metapkgid)
                elif type == u'default':
                    self.default_metapkgs[id].append(metapkgid)
                else:
                    self.debugprint('%s not optional, default or mandatory - ignoring' % metapkgid)
                    
        
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
                        newlist.append(id)
                else:
                    self.debugprint('Invalid group id %s' % id)
            self.sub_groups[key] = newlist
        
        for key in self.mandatory_metapkgs.keys():
            newlist = []
            for id in self.mandatory_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(id)
                else:
                    self.debugprint('Invalid metapkg id %s' % id)
            self.mandatory_metapkgs[key] = newlist
            
        for key in self.default_metapkgs.keys():
            newlist = []
            for id in self.default_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(id)
                else:
                    self.debugprint('Invalid metapkg id %s' % id)
            self.default_metapkgs[key] = newlist

        for key in self.optional_metapkgs.keys():
            newlist = []
            for id in self.optional_metapkgs[key]:
                if self.group_by_id.has_key(id):
                    if not self.group_by_id[id] in newlist:
                        newlist.append(id)
                else:
                    self.debugprint('Invalid metapkg id %s' % id)
            self.optional_metapkgs[key] = newlist

            
    def _installedgroups(self):
        for id in self.grouplist:
            if len(self.mandatory_pkgs[id]) > 0:
                groupinstalled = 1
                for reqpkg in self.mandatory_pkgs[id]:
                    if not self.installed_pkgs.has_key(reqpkg):
                        groupinstalled = 0
                        break
                self.group_installed[id]=groupinstalled
            else:
                groupinstalled = 0
                for anypkg in self.optional_pkgs[id] + self.default_pkgs[id]:
                    if self.installed_pkgs.has_key(anypkg):
                        groupinstalled = 1
                        break
                self.group_installed[id]=groupinstalled
                
        # now we need to check metapkgs in the groups and see which are mandatory
        # and make sure they're installed if they are
        # if there is a mandatory metapkg and it's not installed then the
        # group that includes it is not installed
        # again - mandatory_metapkgs are just figments - nothing more
        for id in self.grouplist:
            for metapkg in self.mandatory_metapkgs[id]:
                if not self.group_installed[metapkg]:
                    self.group_installed[id]=0
                    break
        
    def _get_installed(self, pkgs):
        for (n, a, e, v, r) in pkgs:
            self.installed_pkgs[n] = 1
        
    
    def matchGroup(self, name):
        """takes a name and returns the group id it most likely belongs to for searching"""
        if self.group_by_id.has_key(name):
            return name
        elif self.id_by_name.has_key(name):
            return self.id_by_name[name]
        else:
            return None # let the chips fall where they may (maybe we should raise an exception here)
    
    def groupExists(self, name):
        if self.matchGroup(name):
            return 1
        
        return 0
        
    def isGroupInstalled(self, groupname):
        id = self.matchGroup(groupname)
        return self.group_installed[id]
    
    def groupTree(self, groupname):
        """returns list of all groups, recursively, needed by groupname"""
        id = self.matchGroup(groupname)
        grouplist = [id] 
        grouplist.extend(self.sub_groups[id])
        grouplist.extend(self.mandatory_metapkgs[id])
        grouplist.extend(self.default_metapkgs[id])
        
        for subgroup in grouplist:
            for group in self.sub_groups[subgroup] + self.mandatory_metapkgs[subgroup] + self.default_metapkgs[subgroup]:
                if group not in grouplist:
                    grouplist.append(group)
        
        return grouplist
        
    def pkgTree(self, groupname):
        """get all pkgs in mandatory and default for all groups and their required 
           groups and metapkgs etc, recursing"""
        id = self.matchGroup(groupname)
        grouplist = self.groupTree(id)
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
        
        id = self.matchGroup(groupname)           
        pkglist = []
        for pkg in self.default_pkgs[id] + self.mandatory_pkgs[id]:
            if pkg not in pkglist:
                pkglist.append(pkg)
                
        return pkglist
        
    def requiredGroups(self, groupname):
        """return a list of required groups for this group. Do not recurse 
        through the groups"""
        id = self.matchGroup(groupname)        
        grplist = []
        for group in self.sub_groups[id] + self.mandatory_metapkgs[id] + self.default_metapkgs[id]:
            if group not in grplist:
                grplist.append(group)
         
        return grplist
    
            
    def debugprint(self, msg):
        if self.debug:
            print msg

    def allPkgs(self, groupname):
        """duh - return list of all pkgs in group"""
        id = self.matchGroup(groupname)        
        pkglist = self.requiredPkgs(id) + self.optional_pkgs[id]
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
            try:
                self.pkgs_per_group[group].sort()
            except KeyError:
                print 'Error: Empty Group %s' % group
            else:
                for pkg in self.pkgs_per_group[group]:
                    print '   %s' % pkg
                


def main(pkgtuples):
    compsgrpfun = Groups_Info(pkgtuples, overwrite_groups)
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
    import rpm
    overwrite_groups = 1
    ts = rpm.TransactionSet()
    ts.setVSFlags(-1)
    mi = ts.dbMatch()
    pkgtuples = []
    for hdr in mi:
        if hdr['epoch'] is None:
            epoch = 0
        else:
            epoch = hdr['epoch']
            
        pkgtuples.append((hdr['name'], hdr['arch'], epoch, hdr['version'],
                          hdr['release']))
                          
    main(pkgtuples)
