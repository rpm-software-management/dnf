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
# Copyright 2005 Duke University

import sys
from constants import *
from cElementTree import iterparse
import exceptions


lang_attr = '{http://www.w3.org/XML/1998/namespace}lang'

def parse_boolean(strng):
    if BOOLEAN_STATES.has_key(strng.lower()):
        return BOOLEAN_STATES[strng.lower()]
    else:
        return False
        
class CompsException(exceptions.Exception):
    pass
        
class Group(object):
    def __init__(self, elem=None):
        self.user_visible = True
        self.default = False
        self.selected = False
        self.name = ""
        self.description = ""
        self.translated_name = {}
        self.translated_description = {}
        self.mandatory_packages = {}
        self.optional_packages = {}
        self.default_packages = {}
        self.langonly = None ## what the hell is this?
        self.groupid = None
        

        if elem:
            self.parse(elem)
        
    def __str__(self):
        return self.name
    
    def _packageiter(self):
        lst = self.mandatory_packages.keys() + \
              self.optional_packages.keys() + \
              self.default_packages.keys()
        
        return lst
    
    packages = property(_packageiter)
    
    def nameByLang(self, lang):
        if self.translated_name.has_key[lang]:
            return self.translated_name[lang]
        else:
            return self.name


    def descriptionByLang(self, lang):
        if self.translated_description.has_key[lang]:
            return self.translated_description[lang]
        else:
            return self.description

    def parse(self, elem):
        for child in elem:

            if child.tag == 'id':
                id = child.text
                if self.groupid is not None:
                    raise CompsException
                self.groupid = id
            
            elif child.tag == 'name':
                text = child.text
                if text:
                    text = text.encode('utf8')
                
                lang = child.attrib.get(lang_attr)
                if lang:
                    self.translated_name[lang] = text
                else:
                    self.name = text
    
    
            elif child.tag == 'description':
                text = child.text
                if text:
                    text = text.encode('utf8')
                    
                lang = child.attrib.get(lang_attr)
                if lang:
                    self.translated_description[lang] = text
                else:
                    self.description = text
    
            elif child.tag == 'uservisible':
                self.user_visible = parse_boolean(child.text)
    
            elif child.tag == 'default':
                self.default = parse_boolean(child.text)
    
            elif child.tag == 'langonly': ## FIXME - what the hell is langonly?
                text = child.text
                if self.langonly is not None:
                    raise CompsException
                self.langonly = text
    
            elif child.tag == 'packagelist':
                self.parse_package_list(child)
    
    def parse_package_list(self, packagelist_elem):
        for child in packagelist_elem:
            if child.tag == 'packagereq':
                type = child.attrib.get('type')
                if not type:
                    type = u'mandatory'

                if type not in ('mandatory', 'default', 'optional'):
                    raise CompsException

                package = child.text
                if type == 'mandatory':
                    self.mandatory_packages[package] = 1
                elif type == 'default':
                    self.default_packages[package] = 1
                elif type == 'optional':
                    self.optional_packages[package] = 1

    def add(self, obj):
        """Add another group object to this object"""
    
        # we only need package lists and any translation that we don't already
        # have
        
        for pkg in obj.mandatory_packages.keys():
            self.mandatory_packages[pkg] = 1
        for pkg in obj.default_packages.keys():
            self.default_packages[pkg] = 1
        for pkg in obj.optional_packages.keys():
            self.optional_packages[pkg] = 1
        
        # name and description translations
        for lang in obj.translated_name.keys():
            if not self.translated_name.has_key(lang):
                self.translated_name[lang] = obj.translated_name[lang]
        
        for lang in obj.translated_description.keys():
            if not self.translated_description.has_key(lang):
                self.translated_description[lang] = obj.translated_description[lang]
        
        
        


class Category(object):
    def __init__(self, elem=None):
        self.name = ""
        self.categoryid = None
        self.description = ""
        self.translated_name = {}
        self.translated_description = {}
        self._groups = {}        

        if elem:
            self.parse(elem)
            
    def __str__(self):
        return self.name
    
    def _groupiter(self):
        return self._groups.keys()
    
    groups = property(_groupiter)
    
    def parse(self, elem):
        for child in elem:
            if child.tag == 'id':
                id = child.text
                if self.categoryid is not None:
                    raise CompsException
                self.categoryid = id

            elif child.tag == 'name':
                text = child.text
                if text:
                    text = text.encode('utf8')
                    
                lang = child.attrib.get(lang_attr)
                if lang:
                    self.translated_name[lang] = text
                else:
                    self.name = text
    
            elif child.tag == 'description':
                text = child.text
                if text:
                    text = text.encode('utf8')
                    
                lang = child.attrib.get(lang_attr)
                if lang:
                    self.translated_description[lang] = text
                else:
                    self.description = text
            
            elif child.tag == 'grouplist':
                self.parse_group_list(child)

    def parse_group_list(self, grouplist_elem):
        for child in grouplist_elem:
            if child.tag == 'groupid':
                groupid = child.text
                self._groups[groupid] = 1

    def add(self, obj):
        """Add another category object to this object"""
    
        for grp in obj.groups:
            self._groups[grp] = 1
        
        # name and description translations
        for lang in obj.translated_name.keys():
            if not self.translated_name.has_key(lang):
                self.translated_name[lang] = obj.translated_name[lang]
        
        for lang in obj.translated_description.keys():
            if not self.translated_description.has_key(lang):
                self.translated_description[lang] = obj.translated_description[lang]

        
class Comps:
    def __init__(self, overwrite_groups=False):
        self.groups = {}
        self.categories = {}
        self.compscount = 0
        self.overwrite_groups = overwrite_groups
        
    def add(self, srcfile = None):
        if not srcfile:
            raise CompsException
            
        if type(srcfile) == type('str'):
            # srcfile is a filename string
            infile = open(srcfile, 'rt')
        else:
            # srcfile is a file object
            infile = srcfile
        
        self.compscount += 1
        
        parser = iterparse(infile)

        for event, elem in parser:
            if elem.tag == "group":
                group = Group(elem)
                if self.groups.has_key(group.groupid):
                    thatgroup = self.groups[group.groupid]
                    thatgroup.add(group)
                else:
                    self.groups[group.groupid] = group

            if elem.tag == "category":
                category = Category(elem)
                print category.categoryid
                if self.categories.has_key(category.categoryid):
                    thatcat = self.categories[category.categoryid]
                    thatcat.add(category)
                else:
                    self.categories[category.categoryid] = category
        
        del parser
        


def main():

    try:
        print sys.argv[1]
        p = Comps()
        for srcfile in sys.argv[1:]:
            p.add(srcfile)

        for group in p.groups.values():
            print group
            for pkg in group.packages:
                print '  ' + pkg
        
        for category in p.categories.values():
            print category.name
            for group in category.groups:
                print '  ' + group
                
    except IOError:
        print >> sys.stderr, "newcomps.py: No such file:\'%s\'" % sys.argv[1]
        sys.exit(1)
        
if __name__ == '__main__':
    main()

