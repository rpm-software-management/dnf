import libxml2
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

#TODO: document everything here

class MDParser:

    def __init__(self, filename):

        # Set up mapping of meta types to handler classes 
        handlers = {
            'metadata': PrimaryEntry,
            'filelists': FilelistsEntry,
            'otherdata': OtherEntry,
        }
            
        self.reader = libxml2.newTextReaderFilename(filename)
        self.total = None
        self.count = 0
        self._handlercls = None

        # Read in type, set package node handler and get total number of
        # packages
        while self.reader.Read():
            if self.reader.NodeType() != 1:
                continue

            # Read the metadata type and determine handler class
            metadatatype = self.reader.LocalName()
            self._handlercls = handlers.get(metadatatype, None)

            if not self._handlercls:
                raise ValueError('Unknown repodata type "%s" in %s' % (
                    metadatatype, filename))
           
            # Get the total number of packages
            try:
                self.total = int(self.reader.GetAttribute('packages'))
            except ValueError: 
                pass
        
            break

        # Handle broken input
        if not self._handlercls:
            raise ValueError('no valid repository metadata found in %s' % (
                filename))

    def __iter__(self):
        return self

    def next(self):
        while self.reader.Read():

            name = self.reader.LocalName()
            if name != 'package':
                continue

            self.count += 1
            return self._handlercls(self.reader)

        raise StopIteration


class BaseEntry:
    def __init__(self, reader):
        self._p = {} 

    def __getitem__(self, k):
        return self._p[k]

    def keys(self):
        return self._p.keys()

    def values(self):
        return self._p.values()

    def has_key(self, k):
        return self._p.has_key(k)

    def __str__(self):
        out = StringIO()
        keys = self.keys()
        keys.sort()
        for k in keys:
            out.write('%s=%s\n' % (k, self[k]))
        return out.getvalue()

    def _props(self, reader, keyprefix=''):
        if not reader.HasAttributes(): return {}
        propdict = {}
        reader.MoveToFirstAttribute()
        while 1:
            propdict[keyprefix+reader.LocalName()] = reader.Value()
            if not reader.MoveToNextAttribute(): break
        reader.MoveToElement()
        return propdict
        
    def _value(self, reader):
        if reader.IsEmptyElement(): return ''
        val = ''
        while reader.Read():
            if reader.NodeType() == 3: val += reader.Value()
            else: break
        return val

    def _propswithvalue(self, reader, keyprefix=''):
        out = self._props(reader, keyprefix)
        out[keyprefix+'value'] = self._value(reader)
        return out

    def _getFileEntry(self, reader):
        type = 'file'
        props = self._props(reader)
        if props.has_key('type'): type = props['type']
        value = self._value(reader)
        return (type, value)

class PrimaryEntry(BaseEntry):
    def __init__(self, reader):

        BaseEntry.__init__(self, reader)

        # Avoid excess typing :)
        p = self._p

        self.prco = {}
        self.files = {}

        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()

            if name in ('name', 'arch', 'summary', 'description', 'url', 
                    'packager'): 
                p[name] = self._value(reader)

            elif name == 'version': 
                p.update(self._props(reader))

            elif name in ('time', 'size'):
                p.update(self._props(reader, name+'_'))

            elif name in ('checksum', 'location'): 
                p.update(self._propswithvalue(reader, name+'_'))
            
            elif name == 'format': 
                self.setFormat(reader)

        p['pkgId'] = p['checksum_value']

    def setFormat(self, reader):

        # Avoid excessive typing :)
        p = self._p

        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'format':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()

            if name in ('license', 'vendor', 'group', 'buildhost',
                        'sourcerpm'):
                p[name] = self._value(reader)

            elif name in ('provides', 'requires', 'conflicts', 
                          'obsoletes'):
                self.setPrco(reader)

            elif name == 'header-range':
                p.update(self._props(reader, 'rpm_header_'))

            elif name == 'file':
                (type, value) = self._getFileEntry(reader)
                self.files[value] = type

    def setPrco(self, reader):
        members = []
        myname = reader.LocalName()
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == myname:
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            members.append(self._props(reader))
        self.prco[myname] = members
        
        
class FilelistsEntry(BaseEntry):
    def __init__(self, reader):
        BaseEntry.__init__(self, reader)
        self._p['pkgId'] = reader.GetAttribute('pkgid')
        self.files = {}

        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name == 'file':
                (type, value) = self._getFileEntry(reader)
                self.files[value] = type
                
class OtherEntry(BaseEntry):
    def __init__(self, reader):
        BaseEntry.__init__(self, reader)

        self._p['pkgId'] = reader.GetAttribute('pkgid')
        self._p['changelog'] = []
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name == 'changelog':
                entry = self._props(reader)
                entry['value'] = self._value(reader)
                self._p['changelog'].append(entry)




def test():
    import sys

    parser = MDParser(sys.argv[1])

    for pkg in parser:
        print '-' * 40
        print pkg
        pass

    print parser.total
    print parser.count

if __name__ == '__main__':
    test()
