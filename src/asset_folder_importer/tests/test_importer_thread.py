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
        self.assertEqual(result,['/path/to/myfile.xml', '/path/to/myfile.xmp', '/path/to/myfile.meta',
                                '/path/to/myfile.XML', '/path/to/myfile.XMP', '/path/to/myfile.mp4.xml',
                                '/path/to/myfile.mp4.xmp', '/path/to/myfile.mp4.meta', '/path/to/myfile.mp4.XML',
                                '/path/to/myfile.mp4.XMP', '/path/to/myfileM01.xml', '/path/to/myfileM01.xmp',
                                '/path/to/myfileM01.meta', '/path/to/myfileM01.XML', '/path/to/myfileM01.XMP'])
        
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

    class FakeResponse(object):
        def __init__(self, content, status):
            self.content = content
            self.status = status
    
        def read(self):
            return self.content
        
    class FakeConnection(object):
        def __init__(self, content, status):
            self._content = content
            self._status = status
            self.jackpot = False
            
        def getresponse(self):
            #return TestImporterThread.FakeResponse(self._content,self._status)
            if self.jackpot:
                return TestImporterThread.FakeResponse(json.dumps({'status': 'ok', 'project': 'KP-1234'}),200)
            else:
                return TestImporterThread.FakeResponse(json.dumps({'status': 'notfound'}), 404)
            
        def request(self, method, url, headers=None):
            import urllib
            url = urllib.unquote(url)
            print url
            if url.endswith('/path/to/my/assetfolder'):
                self.jackpot=True
        
    def test_find_invalid_projectid(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db

        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_",username="circletest",password="testpass")

        with mock.patch('httplib.HTTPConnection') as mock_connection:
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger("tester")
            logger.setLevel(logging.DEBUG)
            i = ImporterThread(None,None,self.FakeConfig({'footage_providers_config': '../../footage_providers.yml'}),dbconn=db, logger=logger)

            mock_connection.side_effect = lambda h,c: self.FakeConnection(json.dumps({'status': 'notfound'}),404)
            result = i.ask_pluto_for_projectid("/path/to/something/invalid/media.mxf")
            self.assertIsNone(result)


    def test_find_valid_projectid(self):
        from asset_folder_importer.asset_folder_vsingester.importer_thread import ImporterThread
        from asset_folder_importer.database import importer_db
        
        with mock.patch('psycopg2.connect') as mock_connect:
            db = importer_db("_test_Version_", username="circletest", password="testpass")
        
        with mock.patch('httplib.HTTPConnection') as mock_connection:
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger("tester")
            logger.setLevel(logging.DEBUG)
            i = ImporterThread(None, None, self.FakeConfig({'footage_providers_config': '../../footage_providers.yml'}),
                               dbconn=db, logger=logger)
            
            mock_connection.side_effect = lambda h, c: self.FakeConnection(json.dumps({'status': 'notfound'}), 404)
            result = i.ask_pluto_for_projectid("/path/to/my/assetfolder/with/subdirectories/media.mxf")
            self.assertEqual(result,'KP-1234')


            result = i.ask_pluto_for_projectid("/path/to/my/assetfolder/media.mxf")
            self.assertEqual(result, 'KP-1234')