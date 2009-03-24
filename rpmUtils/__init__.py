#!/usr/bin/python -tt


class RpmUtilsError(Exception):

    """ Exception thrown for anything rpmUtils related. """

    def __init__(self, args=None):
        Exception.__init__(self, args)
