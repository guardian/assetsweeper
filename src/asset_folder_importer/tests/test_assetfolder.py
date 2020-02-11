
import unittest
import os
import threading
import mock
import logging
import http.client
import json


class TestAssetfolder(unittest.TestCase):
    class FakeResponse(object):
        def __init__(self,content,status):
            self.content = content
            self.status = status
            
        def read(self):
            return self.content
        
    def test_locator_valid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator
        
        conn = http.client.HTTPConnection('localhost',8080)
        okstatus=json.dumps({"status": "ok","path": "/path/to/my/asset_folder","project": "VX-13"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(okstatus,200))
        conn.request = mock.MagicMock()
        conn.connect = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password',http_client=conn)
        
        project_id = l.find_assetfolder('/path/to/my/asset_folder')
        self.assertEqual(project_id, "VX-13")


    def test_locator_invalid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, ProjectNotFound
        
        conn = http.client.HTTPConnection('localhost', 8080)
        errstatus = json.dumps({"status": "notfound"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(errstatus, 404))
        conn.request = mock.MagicMock()
        conn.connect = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password', http_client=conn)
        
        self.assertRaises(ProjectNotFound,l.find_assetfolder,'/path/to/my/asset_folder')
 
    def test_locator_error(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, SweeperHTTPError
        
        conn = http.client.HTTPConnection('localhost', 8080)
        errstatus = json.dumps({"status": "error", "error": "some trace"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(errstatus, 500))
        conn.request = mock.MagicMock()
        conn.connect = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password', http_client=conn)
        
        self.assertRaises(SweeperHTTPError,l.find_assetfolder,'/path/to/my/asset_folder')
            
        # self.assertEqual(ex.exception.response.status, 500)
        # self.assertEqual(ex.exception.url, "http://localhost:80/gnm_asset_folder/lookup?path=%2Fpath%2Fto%2Fmy%2Fasset_folder")