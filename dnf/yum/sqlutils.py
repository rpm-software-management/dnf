#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License
# as published by the Free Software Foundation
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

"""
utility functions to handle differences in pysqlite versions
These are from Wichert Akkerman <wichert@deephackmode.org>'s python-dhm
http://www.wiggy.net/code/python-dhm
"""

try:
    import sqlite3 as sqlite
except ImportError:
    import sqlite

class TokenizeError(Exception):
    """Tokenizer error class"""
    pass

def Tokenize(str, whitespace=" \t\r\n", quotes="\"", escapes="\\"):
    """String tokenizer

    This function tokenizes a string while taking quotation and
    escaping into account.

      >>> import dhm.strtools
      >>> dhm.strtools.Tokenize("this is a test")
      ['this', 'is', 'a', 'test']
      >>> dhm.strtools.Tokenize("this \"is a\" test")
      ['this', 'is a', 'test']
      >>> dhm.strtools.Tokenize("this \\\"is\\\" a test")
      ['this', '"is"', 'a', 'test']
      >>> dhm.strtools.Tokenize("this \"is a test")
      Traceback (most recent call last):
        File "<stdin>", line 1, in ?
        File "/usr/local/lib/python2.2/site-packages/dhm/strtools.py", line 80, in Tokenize
          raise TokenizeError, "Unexpected end of string in quoted text"
      dhm.strtools.TokenizeError: Unexecpted end of string in quoted text

    @param        str: string to tokenize
    @type         str: string
    @param whitespace: whitespace characters seperating tokens
    @type  whitespace: string
    @param     quotes: legal quoting characters
    @type      quotes: string
    @param    escapes: characters which can escape quoting characters
    @type     escapes: string
    @return: list of tokens
    @rtype:  sequence of strings
    """
    (buffer, tokens, curtoken, quote)=(str, [], None, None)

    try:
        while buffer:
            if buffer[0]==quote:
                quote=None
            elif (quote==None) and (buffer[0] in quotes):
                quote=buffer[0]
            elif buffer[0] in whitespace:
                if quote!=None:
                    curtoken+=buffer[0]
                else:
                    tokens.append(curtoken)
                    curtoken=None
                    while buffer[1] in whitespace:
                        buffer=buffer[1:]
            elif buffer[0] in escapes:
                if curtoken==None:
                    curtoken=buffer[1]
                else:
                    curtoken+=buffer[1]
                buffer=buffer[1:]
            else:
                if curtoken==None:
                    curtoken=buffer[0]
                else:
                    curtoken+=buffer[0]

            buffer=buffer[1:]
    except IndexError:
        raise TokenizeError, "Unexpected end of string"
    
    if quote:
        raise TokenizeError, "Unexpected end of string in quoted text"

    if curtoken!=None:
        tokens.append(curtoken)

    return tokens


def QmarkToPyformat(query, params):
    """Convert from qmark to pyformat parameter style.

    The python DB-API 2.0 specifies four different possible parameter
    styles that can be used by drivers. This function converts from the
    qmark style to pyformat style.

    @param  query: SQL query to transform
    @type   query: string
    @param params: arguments to query
    @type  params: sequence of strings
    @return: converted query and parameters
    @rtype:  tuple with the new command and a dictionary of arguments
    """
    tokens=Tokenize(query, quotes="'")
    output=[]
    count=1
    for token in tokens:
        if token.endswith("?"):
            output.append(token[:-1] + "%%(param%d)s" % count)
            count+=1
        elif token.endswith("?,") or token.endswith("?)"):
            ntoken = token[:-2] + "%%(param%d)s" % count
            ntoken += token[-1]
            output.append(ntoken)
            count+=1
        else:
            output.append(token)

    dict={}
    count=1
    for param in params:
        dict["param%d" % count]=param
        count+=1
    
    return (" ".join(output), dict)


def executeSQLPyFormat(cursor, query, params=None):
    """
    Execute a python < 2.5 (external sqlite module) style query.

    @param cursor: A sqlite cursor
    @param query: The query to execute
    @param params: An optional list of parameters to the query
    """
    if params is None:
        return cursor.execute(query)

    # Leading whitespace confuses QmarkToPyformat()
    query = query.strip()
    (q, p) = QmarkToPyformat(query, params)
    return cursor.execute(q, p)

def executeSQLQmark(cursor, query, params=None):
    """
    Execute a python 2.5 (sqlite3) style query.

    @param cursor: A sqlite cursor
    @param query: The query to execute
    @param params: An optional list of parameters to the query
    """
    if params is None:
        return cursor.execute(query)
    
    return cursor.execute(query, params)

if sqlite.version_info[0] > 1:
    executeSQL = executeSQLQmark
else:
    executeSQL = executeSQLPyFormat


def sql_esc(pattern):
    """ Apply SQLite escaping, if needed. Returns pattern and esc. """
    esc = ''
    if "_" in pattern or "%" in pattern:
        esc = ' ESCAPE "!"'
        pattern = pattern.replace("!", "!!")
        pattern = pattern.replace("%", "!%")
        pattern = pattern.replace("_", "!_")
    return (pattern, esc)

def sql_esc_glob(patterns):
    """ Converts patterns to SQL LIKE format, if required (or gives up if
        not possible). """
    ret = []
    for pattern in patterns:
        if '[' in pattern: # LIKE only has % and _, so [abc] can't be done.
            return []      # So Load everything

        # Convert to SQL LIKE format
        (pattern, esc) = sql_esc(pattern)
        pattern = pattern.replace("*", "%")
        pattern = pattern.replace("?", "_")
        ret.append((pattern, esc))
    return ret
