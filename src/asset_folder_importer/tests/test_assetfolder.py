from __future__ import absolute_import
import unittest
import mock
import requests
import responses
import json


class TestAssetfolder(unittest.TestCase):
    class FakeResponse(object):
        def __init__(self,content,status):
            self.content = content
            self.status = status
            
        def read(self):
            return self.content

    @responses.activate
    def test_locator_valid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator

        okstatus={"status": "ok","path": "/path/to/my/asset_folder","project": "VX-13"}

        responses.add(responses.GET, "http://localhost:80/gnm_asset_folder/lookup", json=okstatus)
        l = AssetFolderLocator(passwd='fake_password')
        
        project_id = l.find_assetfolder('/path/to/my/asset_folder')
        self.assertEqual(project_id, "VX-13")

    @responses.activate
    def test_locator_invalid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, ProjectNotFound

        errstatus = json.dumps({"status": "notfound"})
        responses.add(responses.GET, "http://localhost:80/gnm_asset_folder/lookup", json=errstatus,status=404)
        
        l = AssetFolderLocator(passwd='fake_password')
        
        self.assertRaises(ProjectNotFound,l.find_assetfolder,'/path/to/my/asset_folder')

    @responses.activate
    def test_locator_error(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, HTTPError

        errstatus = json.dumps({"status": "error", "error": "some trace"})
        responses.add(responses.GET, "http://localhost:80/gnm_asset_folder/lookup", json=errstatus,status=500)

        
        l = AssetFolderLocator(passwd='fake_password')
        
        self.assertRaises(HTTPError,l.find_assetfolder,'/path/to/my/asset_folder')
            
        # self.assertEqual(ex.exception.response.status, 500)
        # self.assertEqual(ex.exception.url, "http://localhost:80/gnm_asset_folder/lookup?path=%2Fpath%2Fto%2Fmy%2Fasset_folder")