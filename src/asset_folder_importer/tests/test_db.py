from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging
import httplib
import json

from asset_folder_importer.database import importer_db


class TestDatabase(unittest.TestCase):
    def test_update_small_fileid(self):
        """
        test that the database module doesn't throw exceptions on different sized id numbers
        :return:
        """
        small_file_id=379311582
        
        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_", username="circletest", password="testpass")
            
        db.update_file_vidispine_id(small_file_id,'VX-1234')

        large_file_id = 37931158242397423792L
        db.update_file_vidispine_id(large_file_id, 'VX-1234')