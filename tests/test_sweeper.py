__author__ = 'dave'

import unittest
import logging

class TestSweeper(unittest.TestCase):
    def __init__(self,*args,**kwargs):
        super(TestSweeper,self).__init__(*args,**kwargs)
        self._cached_id = None


    def test_posix_get_mime(self):

        import sys
        sys.path.insert(0, '../src/')

        from asset_folder_sweeper import posix_get_mime

        filepath = "/etc/hosts"

        self.assertEqual(posix_get_mime(filepath),"text/plain")