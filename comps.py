#!/usr/bin/python2.2
# -*- mode: python -*-


import libxml2
import signal
import getopt
import sys
import exceptions
import string
TRUE=1
FALSE=0


def totext(nodelist):
    return nodelist
# FIXME: I don't think this is relevant with libxml2
#    return string.join(map(lambda node: node.toxml(), nodelist), '')


def parse_boolean(s):
    lower = string.lower (s)
    if lower == 'yes' or lower == 'true':
        return TRUE
    return FALSE


class CompsException (exceptions.Exception):
    pass

class Group:
    def __init__ (self, comps, node = None):
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
        
        if not node == None:
            self.parse (node)

    def parse (self, group_node):
        node = group_node.children

        while node != None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == 'name':
                lang = node.prop('lang')
                if lang:
                    self.translated_name[lang] = totext(node.content)
                else:
                    self.name = totext(node.content)
            elif node.name == 'id':
                id = totext(node.content)
                if self.id is not None:
                    raise CompsException
                self.id = id
            elif node.name == 'description':
                lang = node.prop ('lang')
                if lang:
                    self.translated_description[lang] = totext (node.content)
                else:
                    self.description = totext (node.content)
            elif node.name == 'uservisible':
                if parse_boolean (totext (node.content)):
                    self.user_visible = TRUE
                else:
                    self.user_visible = FALSE
            elif node.name == 'default':
                if parse_boolean (totext (node.content)):
                    self.default = TRUE
                else:
                    self.default = FALSE
            elif node.name == 'requires':
                # FIXME: this isn't in use anymore
                text = totext (node.content)
                if text in self.requires:
                    raise CompsException
                self.requires.append (text)
            elif node.name == 'langonly':
                text = totext (node.content)
                if self.langonly is not None:
                    raise CompsException
                self.langonly = text
            elif node.name == 'packagelist':
                self.parse_package_list (node)
            elif node.name == 'grouplist':
                self.parse_group_list (node)
            node = node.next
                
    def parse_package_list (self, package_node):
        node = package_node.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == 'packagereq':
                type = node.prop ('type')
                if not type:
                    type = u'mandatory'
                if type != 'mandatory' and type != 'default' and type != 'optional':
                    raise CompsException
                package = totext (node.content)
                self.packages[package] = (type, package)

                # see note above about the hack this is.
                reqs = node.prop ('requires')
                if reqs is not None:
                    self.pkgConditionals[package] = reqs
            node = node.next

    def parse_group_list (self, group_node):
        node = group_node.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == 'groupreq':
                type = node.prop ('type')
                if not type:
                    type = u'mandatory'
                if type != 'mandatory' and type != 'default' and type != 'optional':
                    raise CompsException
                group = totext (node.content)
                self.groups[group] = (type, group)
            elif node.name == 'metapkg':
                type = node.prop ('type')
                if not type:
                    type = u'default'
                if type != 'default' and type != 'optional':
                    raise CompsException
                group = totext (node.content)
                self.metapkgs[group] = (type, group)
                
            node = node.next

    def sanity_check (self):
        if not self.comps:
            raise CompsException
        if not self.name:
            raise CompsException
        for (type, package) in self.packages.values ():
            try:
                self.comps.packages[package]
            except KeyError:
                pass
#                raise CompsException
            

class Package:
    def __init__ (self, comps, node = None):
        self.comps = comps
        self.name=None
        self.version=None
        self.supported=FALSE
        self.excludearch=None
        self.dependencies=[]
        self.installed = 0
        if node:
            self.parse (node)

    def sanity_check (self):
        if self.name == None:
            return FALSE

    def parse_dependency_list (self, package_node):
        node = package_node.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == 'dependency':
                self.dependencies.append(totext (node.content))
            node = node.next

    def parse (self, group_node):
        node = group_node.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == 'name':
                self.name = totext (node.content)
            elif node.name == 'version':
                self.version = totext (node.content)
            elif node.name == 'excludearch':
                self.excludearch = totext (node.content)
            elif node.name == 'packagelist':
                self.parse_package_list (node)
            elif node.name == 'supported':
                if parse_boolean (totext (node.content)):
                    self.supported = TRUE
                else:
                    self.supported = FALSE
            elif node.name == 'dependencylist':
                self.parse_dependency_list(node)
            node = node.next

class GroupHierarchy (dict):
    def __init__(self, comps, node):
        self.comps = comps
        self.order = []
        self.translations = {}
        if node:
            self.parse(node)

    def parse(self, main_node):
        node = main_node.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == "category":
                self.parse_category(node)
            else:
                print "unhandled node in <comps.grouphierarchy>: " + node.name
            node = node.next

    def parse_category(self, category_node):
        node = category_node.children
        translations = {}
        subs = []
        name = None
        
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == "name":
                lang = node.prop('lang')
                if lang:
                    translations[lang] = totext(node.content)
                else:
                    name = totext(node.content)
            elif node.name == "subcategories":
                subs.extend(self.parse_subcategories(node))
            else:
                print "unhandled node in <comps.grouphierarchy.category>: " + node.name
            node = node.next

        if name is None:
            raise CompsException, "no name specified"

        if not self.has_key(name):
            self.order.append(name)
            self[name] = subs
        else:
            self[name] = self[name].extend(subs)
        self.translations[name] = translations

    def parse_subcategories(self, category_node):
        node = category_node.children
        ret = []
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            if node.name == "subcategory":
                id = totext(node.content)
                if not id:
                    raise CompsException
                ret.append(id)
            else:
                print "unhandled node in <comps.grouphierarchy.parse_category>:" + node.name
            node = node.next
        return ret
                
        

class Comps (object):
    def __init__ (self, filename=None):
        self.groups = {}
        self.packages = {}
        self.hierarchy = {}

        if filename != None:
            self.load (filename)

    def load (self, filename):
        if type(filename) == type('str'):
            doc = libxml2.parseFile (filename)
        else:
            file = filename.read()
            doc = libxml2.parseMemory(file, len(file))
        root = doc.getRootElement()

        node = root.children
        while node is not None:
            if node.type != "element":
                node = node.next
                continue
            
            if node.name == "group":
                group = Group(self, node)
                self.groups[group.name] = group
            elif node.name == "package":
                package = Package (self, node)
                self.packages[package.name] = package
            elif node.name == "grouphierarchy":
                self.hierarchy = GroupHierarchy(self, node)
            else:
                print "unhandled node in <comps>: " + node.name
            node = node.next
 
        doc.freeDoc ()
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

    signal.signal (signal.SIGINT, signal.SIG_DFL)
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
