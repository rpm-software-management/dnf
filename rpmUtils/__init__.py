#!/usr/bin/python -tt

import exceptions


class RpmUtilsError(exceptions.Exception):
    def __init__(self, args=None):
        exceptions.Exception.__init__(self)
        self.args = args
