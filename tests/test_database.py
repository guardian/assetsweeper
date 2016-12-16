__author__ = 'dave'

import unittest
import logging

class TestDatabase(unittest.TestCase):
    def __init__(self,*args,**kwargs):
        super(TestDatabase,self).__init__(*args,**kwargs)
        self._cached_id = None