#!/usr/bin/python2.2
# -*- mode: python -*-

from cElementTree import iterparse
import signal
import getopt
import sys
import exceptions

TRUE=1
FALSE=0

def parse_boolean(s):
    if s.lower() in ('yes', 'true'):
        return TRUE
    return FALSE

def getattrib(elem, key, default=None):
    '''Retrieve an attribute named key from elem. Return default if not found.

    This is required because ElementTree includes namespace information in the
    name of each attribute.
    '''
    for k, v in elem.attrib.iteritems():
        k = k.split('}', 1)[-1]
        if k == key:
            return v
    return default

class CompsException(exceptions.Exception):
    pass

class Group:
    def __init__(self, comps, elem=None):
        self.comps = comps
        self.user_visible = TRUE
        self.default = FALSE
        self.removable = FALSE
        self.name=""
        self.description = ""
        self.translated_name = {}
        self.translated_description = {}
        self.packages = {}
        self.langonly = None
        self.groups = {}
        self.metapkgs = {}
        self.requires = []
        self.id = None

        # FIXME: this is a horrible, horrible hack.  but we can't stick it
        # in with the package without making the tuple larger and that's
        # certain to break something and I don't have time to track them
        # all down.  so we have to keep separate track of any "requirements"
        # the package has to have to be installed.  this is *only* used right
        # now for some i18n packages.  if it gets used for anything else, it
        # is guaranteed to break within anaconda.    jlk - 12 aug 2002
        self.pkgConditionals = {}
        
        if elem:
            self.parse(elem)

    def parse(self, elem):

        for child in elem:
            if child.tag == 'name':
                text = child.text
                if text:
                    text = text.encode('utf8')
                lang = getattrib(child, 'lang')
                if lang:
                    self.translated_name[lang] = text
                else:
                    self.name = text

            elif child.tag == 'id':
                id = child.text
                if self.id is not None:
                    raise CompsException
                self.id = id

            elif child.tag == 'description':
                text = child.text
                if text:
                    text = text.encode('utf8')
                lang = getattrib(child, 'lang')
                if lang:
                    self.translated_description[lang] = text
                else:
                    self.description = text

            elif child.tag == 'uservisible':
                self.user_visible = parse_boolean(child.text)

            elif child.tag == 'default':
                self.default = parse_boolean(child.text)

            elif child.tag == 'requires':
                # FIXME: this isn't in use anymore
                text = child.text
                if text in self.requires:
                    raise CompsException
                self.requires.append(text)

            elif child.tag == 'langonly':
                text = child.text
                if self.langonly is not None:
                    raise CompsException
                self.langonly = text

            elif child.tag == 'packagelist':
                self.parse_package_list(child)

            elif child.tag == 'grouplist':
                self.parse_group_list(child)

    def parse_package_list(self, packagelist_elem):

        for child in packagelist_elem:
            if child.tag == 'packagereq':
                type = child.attrib.get('type')
                if not type:
                    type = u'mandatory'

                if type not in ('mandatory', 'default', 'optional'):
                    raise CompsException

                package = child.text
                self.packages[package] = (type, package)

                # see note above about the hack this is.
                reqs = child.attrib.get('requires')
                if reqs:
                    self.pkgConditionals[package] = reqs

    def parse_group_list(self, grouplist_elem):

        for child in grouplist_elem:
            if child.tag == 'groupreq':
                type = getattrib(child, 'type')
                if not type:
                    type = u'mandatory'

                if type not in ('mandatory', 'default', 'optional'):
                    raise CompsException

                group = child.text
                self.groups[group] = (type, group)

            elif child.tag == 'metapkg':
                type = getattrib(child, 'type')
                if not type:
                    type = u'default'
                if type not in ('default', 'optional'):
                    raise CompsException
                group = child.text
                self.metapkgs[group] = (type, group)
                
    def sanity_check(self):
        if not self.comps:
            raise CompsException
        if not self.name:
            raise CompsException
        for (type, package) in self.packages.values():
            try:
                self.comps.packages[package]
            except KeyError:
                pass
#                raise CompsException
            

class Package:
    def __init__(self, comps, elem=None):
        self.comps = comps
        self.name = None
        self.version = None
        self.supported = FALSE
        self.excludearch = None
        self.dependencies = []
        self.installed = 0
        if elem:
            self.parse(elem)

    def sanity_check(self):
        if self.name == None:
            return FALSE

    def parse_dependency_list(self, packagedeps_elem):
        for child in packagedeps_elem:
            if child.tag == 'dependency':
                self.dependencies.append(child.text)

    def parse(self, group_elem):
        for child in group_elem:
            if child.tag == 'name':
                self.name = child.text

            elif child.tag == 'version':
                self.version = child.text

            elif child.tag == 'excludearch':
                self.excludearch = child.text

            elif child.tag == 'packagelist':
                self.parse_package_list(child)

            elif child.tag == 'supported':
                self.supported = parse_boolean(child.text)

            elif child.tag == 'dependencylist':
                self.parse_dependency_list(child)

class GroupHierarchy(dict):
    def __init__(self, comps, elem=None):
        self.comps = comps
        self.order = []
        self.translations = {}
        if elem:
            self.parse(elem)

    def parse(self, elem):
        for child in elem:
            if child.tag == "category":
                self.parse_category(child)
            else:
                print "unhandled node in <comps.grouphierarchy>: " + child.tag

    def parse_category(self, category_elem):
        translations = {}
        subs = []
        name = None
        
        for child in category_elem:
            if child.tag == "name":
                text = child.text
                if text:
                    text = text.encode('utf8')
                lang = getattrib(child, 'lang')
                if lang:
                    translations[lang] = text
                else:
                    name = text

            elif child.tag == "subcategories":
                subs.extend(self.parse_subcategories(child))

            else:
                print "unhandled node in <comps.grouphierarchy.category>: " + \
                        elem.tag

        if not name:
            raise CompsException, "no name specified"

        if not self.has_key(name):
            self.order.append(name)
            self[name] = subs
        else:
            self[name] = self[name].extend(subs)
        self.translations[name] = translations

    def parse_subcategories(self, category_elem):
        ret = []
        for child in category_elem:
            if child.tag == "subcategory":
                id = child.text
                if not id:
                    raise CompsException
                ret.append(id)
            else:
                print "unhandled node in <comps.grouphierarchy.parse_category>:" + child.tag

        return ret
                
        

class Comps(object):
    def __init__(self, srcfile=None):
        self.groups = {}
        self.packages = {}
        self.hierarchy = {}

        if srcfile != None:
            self.load(srcfile)

    def load(self, srcfile):
        if type(srcfile) == type('str'):
            # srcfile is a filename string
            infile = open(srcfile, 'rt')
        else:
            # srcfile is a file object
            infile = srcfile

        parser = iterparse(infile)

        for event, elem in parser:
            if elem.tag == "group":
                group = Group(self, elem)
                self.groups[group.name] = group

            elif elem.tag == "package":
                package = Package(self, elem)
                self.packages[package.name] = package

            elif elem.tag == "grouphierarchy":
                self.hierarchy = GroupHierarchy(self, elem)

        if 0:
            for group in self.hierarchy.order:
                print group
                print self.hierarchy[group]
        if 0:
            for group in self.groups.values():
                print group.name
            for package in self.packages.values():
                print package.name
                print package.dependencies
            for group in self.groups.values():
                group.sanity_check()
            for package in self.packages.values():
                package.sanity_check()


usage = "usage: pkggroup.py compsfile.xml"

def main():

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    opts, args = getopt.getopt(sys.argv[1:], '',
                               ['help'])

    for opt, arg in opts:
        if opt == '--help':
            print usage
            sys.exit(0)
    if len(args) != 1:
        print >> sys.stderr, usage
        sys.exit(1)
    try:
        p = Comps(args[0])

    except IOError:
        print >> sys.stderr, "pkggroup.py: No such file:\'%s\'" % args[0]
        sys.exit(1)
if __name__ == '__main__':
    main()
