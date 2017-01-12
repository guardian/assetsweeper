from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging
import httplib
import json


class TestImporterThread(unittest.TestCase):
    class FakeConfig(object):
        def __init__(self, content):
            self._content = content
            
        def value(self, key, noraise=True):
            if not key in self._content:
                return ""
            return self._content[key]
        
    def test_potential_sidecar_filenames(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")

        i = ImporterThread(None,None,self.FakeConfig({'footage_providers_config': '../../footage_providers.yml'}),dbconn=db)
        
        result = map(lambda x: x, i.potentialSidecarFilenames("/path/to/myfile.mp4", isxdcam=False))
        self.assertEqual(result,['/path/to/myfile.xml', '/path/to/myfile.xmp', '/path/to/myfile.meta', '/path/to/myfile.XML',
                                '/path/to/myfile.XMP','/path/to/myfile.mp4.xml','/path/to/myfile.mp4.xmp','/path/to/myfile.mp4.meta',
                                '/path/to/myfile.mp4.XML','/path/to/myfile.mp4.XMP'])
        
        result = map(lambda x: x, i.potentialSidecarFilenames("/path/to/myfile.mp4", isxdcam=True))
        self.assertEqual(result,[])
        
    def test_import_tags(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db
        
        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")
            
        i = ImporterThread(None, None, self.FakeConfig({'footage_providers_config': '../../footage_providers.yml'}),dbconn=db)
        
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/mp4'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'video/quicktime'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'application/mxf'}), ['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'model/vnd.mts'}),['lowres'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/jpeg'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'image/tiff'}), ['lowimage'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'audio/aiff'}), ['lowaudio'])
        self.assertEqual(i.import_tags_for_fileref({'mime_type': 'audio/wav'}), ['lowaudio'])
