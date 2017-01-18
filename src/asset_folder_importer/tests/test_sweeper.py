__author__ = 'dave'

import unittest
import logging

class TestSweeper(unittest.TestCase):
    def __init__(self,*args,**kwargs):
        super(TestSweeper,self).__init__(*args,**kwargs)
        self._cached_id = None


    def test_posix_get_mime(self):

        from asset_folder_sweeper import posix_get_mime

        #filepath = "/etc/hosts"

        #self.assertEqual(posix_get_mime(filepath),"text/plain")

    def test_find_files(self):

        from asset_folder_sweeper import find_files
        from asset_folder_importer.config import configfile

        cfg=configfile("/etc/asset_folder_importer.cfg")

        self.assertGreater(find_files(cfg), 10)