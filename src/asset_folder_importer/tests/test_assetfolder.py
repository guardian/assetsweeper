from __future__ import absolute_import
import unittest
import mock
import requests
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

        okstatus=json.dumps({"status": "ok","path": "/path/to/my/asset_folder","project": "VX-13"})

        result = mock.MagicMock(requests.models.Response)
        result.status_code=200
        result.text = okstatus

        with mock.patch("requests.get",return_value=result):
            l = AssetFolderLocator(passwd='fake_password')

            project_id = l.find_assetfolder('/path/to/my/asset_folder')
            self.assertEqual(project_id, "VX-13")

    def test_locator_invalid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, ProjectNotFound

        errstatus = json.dumps({"status": "notfound"})

        result = mock.MagicMock(requests.models.Response)
        result.status_code=404
        result.text = errstatus

        with mock.patch("requests.get", return_value=result):
            l = AssetFolderLocator(passwd='fake_password')

            self.assertRaises(ProjectNotFound,l.find_assetfolder,'/path/to/my/asset_folder')

    def test_locator_error(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, HTTPError

        errstatus = json.dumps({"status": "error", "error": "some trace"})

        result = mock.MagicMock(requests.models.Response)
        result.status_code=500
        result.text = errstatus

        with mock.patch("requests.get", return_value=result):
            l = AssetFolderLocator(passwd='fake_password')
            self.assertRaises(HTTPError,l.find_assetfolder,'/path/to/my/asset_folder')