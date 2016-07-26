# parser.py
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import dnf.exceptions
import dnf.i18n
import dnf.pycomp
import dnf.util
import logging
import os.path
import re

_KEYCRE = re.compile(r"\$(\w+)|\${(\w+)}")

logger = logging.getLogger("dnf")

def substitute(raw, substs):
    '''Perform variable replacement

    :param raw: String to perform substitution on.
    :param vars: Dictionary of variables to replace. Key is variable name
      (without $ prefix). Value is replacement string.
    :return: Input raw string with substituted values.
    '''

    done = []                      # Completed chunks to return

    while raw:
        m = _KEYCRE.search(raw)
        if not m:
            done.append(raw)
            break

        # Determine replacement value (if unknown variable then preserve
        # original)
        varname = m.group(2).lower() if m.group(2) else m.group(1).lower()
        replacement = substs.get(varname, m.group())

        start, end = m.span()
        done.append(raw[:start])    # Keep stuff leading up to token
        done.append(replacement)    # Append replacement value
        raw = raw[end:]             # Continue with remainder of string

    return ''.join(done)


class ConfigPreProcessor(object):
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


    def __init__(self, configfile, variables=None):
        # put the vars away in a helpful place
        self._vars = variables

        # used to track the current ini-section
        self._section = None

        # set some file-like object attributes for ConfigParser
        # these just make confpp look more like a real file object.
        self.mode = 'r'
        self.name = None

        # first make configfile a url even if it points to
        # a local file
        scheme = dnf.pycomp.urlparse.urlparse(configfile)[0]
        if scheme == '':
            # check it to make sure it's not a relative file url
            if not os.path.isabs(configfile):
                configfile = os.path.abspath(configfile)
            url = 'file://' + configfile
        else:
            url = configfile

        # these are used to maintain the include stack and check
        # for recursive/duplicate includes
        self._incstack = []
        self._alreadyincluded = []

        # _pushfile will return None if it couldn't open the file
        _fo = self._pushfile(url)

    def readline(self, _size=0):
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
        line = ''
        while len(self._incstack) > 0:
            # peek at the file like object on top of the stack
            fo = self._incstack[-1]
            line = fo.readline()
            if len(line) > 0:
                # match include= and includeconf= for compatibility with dnf < 2.0
                m = re.match(r'\s*include(conf)?\s*=\s*(?P<url>.*)', line)
                if m:
                    url = m.group('url')
                    if len(url) == 0:
                        msg = 'Error parsing config %s: '\
                              'include must specify file to include.'
                        raise dnf.exceptions.ConfigError(msg % self.name)
                    else:
                        # whooohoo a valid include line.. push it on the stack
                        fo = self._pushfile(url)
                else:
                    # check if the current line starts a new section
                    secmatch = re.match(r'\s*\[(?P<section>.*)\]', line)
                    if secmatch:
                        self._section = secmatch.group('section')
                    # line didn't match include=, just return it as is
                    # for the ConfigParser
                    break
            else:
                # the current file returned EOF, pop it off the stack.
                self._popfile()

        # if the section is prefixed by a space then it is breaks
        # iniparser/configparser so fix it:
        broken_sec_match = re.match(r'\s+\[(?P<section>.*)\]', line)
        line = dnf.i18n.ucd(line)
        if broken_sec_match:
            line = line.lstrip()
        # at this point we have a line from the topmost file on the stack
        # or EOF if the stack is empty
        if self._vars:
            return substitute(line, self._vars)
        return line


    def _absurl(self, url):
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
            return dnf.pycomp.urlparse.urljoin(self.geturl(), url)

    def _pushfile(self, url):
        """
        Opens the url specified, pushes it on the stack, and
        returns a file like object. Returns None if the url
        has previously been included.
        If the file can not be opened this function writes a warning.
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
            fo = dnf.util._urlopen(absurl, mode='w+')
        except IOError:
            fo = None
        if fo is not None:
            self.name = absurl
            self._incstack.append(fo)
            self._alreadyincluded.append(includetuple)
        else:
            fn = dnf.util.strip_prefix(absurl, 'file://')
            msg = "Can not read configuration: %s , ignoring" % (fn if fn
                                                                 else absurl)
            logger.warning(msg)

        return fo

    def _popfile(self):
        """
        Pop a file off the stack signaling completion of including that file.
        """
        fo = self._incstack.pop()
        fo.close()
        if len(self._incstack) > 0:
            self.name = self._incstack[-1].name
        else:
            self.name = None


    def _isalreadyincluded(self, atuple):
        """
        Checks if the tuple describes an include that was already done.
        This does not necessarily have to be recursive
        """
        for etuple in self._alreadyincluded:
            if etuple == atuple:
                return 1
        return 0


    def geturl(self):
        return self.name
