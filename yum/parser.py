#! /usr/bin/python -tt
import re
import urlparse
import urlgrabber
import os.path

import Errors


_KEYCRE = re.compile(r"\$(\w+)")

def varReplace(raw, vars):
    '''Perform variable replacement

    @param raw: String to perform substitution on.  
    @param vars: Dictionary of variables to replace. Key is variable name
        (without $ prefix). Value is replacement string.
    @return: Input raw string with substituted values.
    '''

    done = []                      # Completed chunks to return

    while raw:
        m = _KEYCRE.search(raw)
        if not m:
            done.append(raw)
            break

        # Determine replacement value (if unknown variable then preserve
        # original)
        varname = m.group(1).lower()
        replacement = vars.get(varname, m.group())

        start, end = m.span()
        done.append(raw[:start])    # Keep stuff leading up to token
        done.append(replacement)    # Append replacement value
        raw = raw[end:]             # Continue with remainder of string

    return ''.join(done)

class ConfigPreProcessor:
    """
    ConfigParser Include Pre-Processor

    File-like Object capable of pre-processing include= lines for
    a ConfigParser. 

    The readline function expands lines matching include=(url)
    into lines from the url specified. Includes may occur in
    included files as well. 

    Suggested Usage::
        cfg = ConfigParser.ConfigParser()
        fileobj = confpp( fileorurl )
        cfg.readfp(fileobj)
    """
    
    
    def __init__(self, configfile, vars=None):
        # put the vars away in a helpful place
        self._vars = vars

        # used to track the current ini-section
        self._section = None
        
        # set some file-like object attributes for ConfigParser
        # these just make confpp look more like a real file object.
        self.mode = 'r' 
        
        # first make configfile a url even if it points to 
        # a local file
        scheme = urlparse.urlparse(configfile)[0]
        if scheme == '':
            # check it to make sure it's not a relative file url
            if configfile[0] != '/':
                configfile = os.getcwd() + '/' + configfile
            url = 'file://' + configfile
        else:
            url = configfile
        
        # these are used to maintain the include stack and check
        # for recursive/duplicate includes
        self._incstack = []
        self._alreadyincluded = []
        
        # _pushfile will return None if he couldn't open the file
        fo = self._pushfile( url )
        if fo is None: 
            raise Errors.ConfigError, 'Error accessing file: %s' % url
        
    def readline( self, size=0 ):
        """
        Implementation of File-Like Object readline function. This should be
        the only function called by ConfigParser according to the python docs.
        We maintain a stack of real FLOs and delegate readline calls to the 
        FLO on top of the stack. When EOF occurs on the topmost FLO, it is 
        popped off the stack and the next FLO takes over. include= lines 
        found anywhere cause a new FLO to be opened and pushed onto the top 
        of the stack. Finally, we return EOF when the bottom-most (configfile
        arg to __init__) FLO returns EOF.
        
        Very Technical Pseudo Code::
        
            def confpp.readline() [this is called by ConfigParser]
                open configfile, push on stack
                while stack has some stuff on it
                    line = readline from file on top of stack
                    pop and continue if line is EOF
                    if line starts with 'include=' then
                        error if file is recursive or duplicate
                        otherwise open file, push on stack
                        continue
                    else
                        return line
                
                return EOF
        """
        
        # set line to EOF initially. 
        line=''
        while len(self._incstack) > 0:
            # peek at the file like object on top of the stack
            fo = self._incstack[-1]
            line = fo.readline()
            if len(line) > 0:
                m = re.match( r'\s*include\s*=\s*(?P<url>.*)', line )
                if m:
                    url = m.group('url')
                    if len(url) == 0:
                        raise Errors.ConfigError, \
                             'Error parsing config %s: include must specify file to include.' % (self.name)
                    else:
                        # whooohoo a valid include line.. push it on the stack
                        fo = self._pushfile( url )
                else:
                    # check if the current line starts a new section
                    secmatch = re.match( r'\s*\[(?P<section>.*)\]', line )
                    if secmatch:
                        self._section = secmatch.group('section')
                    # line didn't match include=, just return it as is
                    # for the ConfigParser
                    break
            else:
                # the current file returned EOF, pop it off the stack.
                self._popfile()
        
        # if the section is prefixed by a space then it is breaks iniparser/configparser
        # so fix it
        broken_sec_match = re.match(r'\s+\[(?P<section>.*)\]', line)
        if broken_sec_match:
            line = line.lstrip()
        # at this point we have a line from the topmost file on the stack
        # or EOF if the stack is empty
        if self._vars:
            return varReplace(line, self._vars)
        return line
    
    
    def _absurl( self, url ):
        """
        Returns an absolute url for the (possibly) relative
        url specified. The base url used to resolve the
        missing bits of url is the url of the file currently
        being included (i.e. the top of the stack).
        """
        
        if len(self._incstack) == 0:
            # it's the initial config file. No base url to resolve against.
            return url
        else:
            return urlparse.urljoin( self.geturl(), url )

    def _pushfile( self, url ):
        """
        Opens the url specified, pushes it on the stack, and 
        returns a file like object. Returns None if the url 
        has previously been included.
        If the file can not be opened this function exits.
        """
        
        # absolutize this url using the including files url
        # as a base url.
        absurl = self._absurl(url)

        # get the current section to add it to the included
        # url's name.
        includetuple = (absurl, self._section)
        # check if this has previously been included.
        if self._isalreadyincluded(includetuple):
            return None
        try:
            fo = urlgrabber.grabber.urlopen(absurl)
        except urlgrabber.grabber.URLGrabError, e:
            fo = None
        if fo is not None:
            self.name = absurl
            self._incstack.append( fo )
            self._alreadyincluded.append(includetuple)
        else:
            raise Errors.ConfigError, \
                  'Error accessing file for config %s' % (absurl)

        return fo
    
    
    def _popfile( self ):
        """
        Pop a file off the stack signaling completion of including that file.
        """
        fo = self._incstack.pop()
        fo.close()
        if len(self._incstack) > 0:
            self.name = self._incstack[-1].geturl()
        else:
            self.name = None
    
    
    def _isalreadyincluded( self, tuple ):
        """
        Checks if the tuple describes an include that was already done.
        This does not necessarily have to be recursive
        """
        for etuple in self._alreadyincluded:
            if etuple == tuple: return 1
        return 0
    
    
    def geturl(self): return self.name
