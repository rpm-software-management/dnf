#!/usr/bin/python -tt

import libxml2
import sys
import os

## read for transactions to push to a transaction class
## must keep track of group, config and packages, - allow for an 'action' 
## attribute for each group and config item

class YumTransaction:
    """describes a yum transaction: 
       config() returns a path to a config file
       pkgsUpdate() returns a list of pkgs to be updated
       pkgsUpgrade() returns a list of pkgs to be upgraded
       pkgsRemove() returns a list of pkgs to be removed
       pkgsInstall() returns a list of pkgs to be installed
       groupsUpdate() returns a list of groups to be updated
       groupsInstall() returns a list of groups to be installed
       """
    def __init__(self, base_node):
        self.groups = {}
        self.pkgs = {}
        self.name = 'my transaction'
        self.config = '/etc/yum.conf' #default
        self.groups['install'] = []
        self.groups['update'] = []
        self.groups['remove'] = []
        self.pkgs['install'] = []
        self.pkgs['update'] = []
        self.pkgs['remove'] = []
        self.pkgs['upgrade'] = []
        self._parseTrans(base_node)
        
    
    def processes(self):
        processlist = []
        groupsprocesslist = []
        for process in ['install', 'update', 'upgrade', 'remove']:
            if len(self.pkgs[process]) > 0:
                processlist.append(process)
        for process in ['install', 'update', 'remove']:
            if len(self.groups[process]) > 0:
                groupsprocesslist.append(process)
        
        return (processlist, groupsprocesslist)
        
    def pkgsUpdate(self):
        return self.pkgs['update']
    
    def pkgsUpgrade(self):
        return self.pkgs['upgrade']
        
    def pkgsInstall(self):
        return self.pkgs['install']

    def pkgsRemove(self):
        return self.pkgs['remove']

    def groupsUpdate(self):
        return self.groups['update']
    
    def groupsInstall(self):
        return self.groups['install']
        
    def _parseTrans(self, base_node):
        props = base_node.properties
        while props:
            if props.name == 'name':
                self.name = props.content
            props = props.next
        node = base_node.children
        while node is not None:
            if node.type != 'element':
                node = node.next
                continue
            

            if node.name == 'config':
                self.config = node.content
            elif node.name == 'group':
                if node.prop('action') in ['update', 'install']:
                    if node.content not in self.groups[node.prop('action')]:
                        self.groups[node.prop('action')].append(node.content)
                else:
                    print 'unknown action type of %s for %s' % (node.prop('action'), node.content)
            elif node.name == 'package':
                if node.prop('action') in ['update', 'install', 'remove', 'upgrade']:
                    if node.content not in self.pkgs[node.prop('action')]:
                        self.pkgs[node.prop('action')].append(node.content)
                else:
                    print 'unknown action type of %s for %s' % (node.prop('action'), node.content)
            node = node.next
            continue
        
class YumTransactionFile:
    """
    describes the whole transaction xml file - list of transactions, etc
    transactionList() returns list of YumTransaction objects
    """
    def __init__(self, filename):
        self.transactions = []
        self.processFile(filename)
        
    def processFile(self, filename):
        try:
            doc = libxml2.parseFile(filename)
        except libxml2.parserError, e:
            print 'Bad file %s - will not parse' % filename
            pass
        else:
            root = doc.getRootElement()
            node = root.children
            while node is not None:
                if node.type != 'element':
                    node = node.next
                    continue
                if node.name == 'transaction':
                    self.transactions.append(YumTransaction(node))
                else:
                    print 'not a transaction'
                node = node.next
                continue
            
    def transactionCount(self):
        return len(self.transactions)
        
    def transactionList(self):
        return self.transactions


def main(file):
    ytx = YumTransactionFile(file)
    tslist = ytx.transactionList()
    
    if len(tslist) == 0:
        print 'no transactions, argh'
        sys.exit(1)
    
    for trans in tslist:
        print 'Transaction:'
        print '  ' + trans.config
        print '  groups:'
        print '   install = ',
        for grp in trans.groupsInstall():
            print grp,
        print '\n   updates = ',
        for grp in trans.groupsUpdate():
            print grp,
        print '\n  packages:'
        print '   updates = ',
        for pkg in trans.pkgsUpdate():
            print pkg,
        print '\n  packages:'
        print '   upgrades = ',
        for pkg in trans.pkgsUpgrade():
            print pkg,

        print '\n   removes = ',
        for pkg in trans.pkgsRemove():
            print pkg,
        print '\n   install = ',
        for pkg in trans.pkgsInstall():
            print pkg,
        print
        
        
        
if __name__ == '__main__':
    main(sys.argv[1])
