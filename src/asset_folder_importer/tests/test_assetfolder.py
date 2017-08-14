from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging
import httplib
import json


class TestSweeperAssetFolder(unittest.TestCase):
    def test_get_assetfolder_working(self):
        """
        get_asset_folder_for should return the asset folder segment for a valid path
        :return:
        """
        from asset_folder_importer.asset_folder_sweeper.assetfolder import get_asset_folder_for

        result = get_asset_folder_for("/srv/Multimedia2/Media Production/Assets/Multimedia_News/Anywhere_But_Westminster_The_New_Series/john_domokos_The_future_of_trade_unions/stills from Strike Day")
        self.assertEqual(result, 'Multimedia_News/Anywhere_But_Westminster_The_New_Series/john_domokos_The_future_of_trade_unions')

    def test_get_assetfolder_invalid(self):
        """
        get_asset_folder_for should return ValueError for an invalid path
        :return:
        """
        from asset_folder_importer.asset_folder_sweeper.assetfolder import get_asset_folder_for

        with self.assertRaises(ValueError) as value_excpt:
            result = get_asset_folder_for("/srv/Proxies2/DAMSYSTEM/invalidpath")
            self.assertEqual(value_excpt.exception, "/srv/Proxies2/DAMSYSTEM/invalidpath does not look like a valid asset folder path")


class TestPlutoAssetfolder(unittest.TestCase):
    class FakeResponse(object):
        def __init__(self,content,status):
            self.content = content
            self.status = status
            
        def read(self):
            return self.content
        
    def test_locator_valid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator
        
        conn = httplib.HTTPConnection('localhost',8080)
        okstatus=json.dumps({"status": "ok","path": "/path/to/my/asset_folder","project": "VX-13"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(okstatus,200))
        conn.request = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password',http_client=conn)
        
        project_id = l.find_assetfolder('/path/to/my/asset_folder')
        self.assertEqual(project_id, "VX-13")


    def test_locator_invalid(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, ProjectNotFound
        
        conn = httplib.HTTPConnection('localhost', 8080)
        errstatus = json.dumps({"status": "notfound"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(errstatus, 404))
        conn.request = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password', http_client=conn)
        
        self.assertRaises(ProjectNotFound,l.find_assetfolder,'/path/to/my/asset_folder')
 
    def test_locator_error(self):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, HTTPError
        
        conn = httplib.HTTPConnection('localhost', 8080)
        errstatus = json.dumps({"status": "error", "error": "some trace"})
        
        conn.getresponse = mock.MagicMock(return_value=self.FakeResponse(errstatus, 500))
        conn.request = mock.MagicMock()
        
        l = AssetFolderLocator(passwd='fake_password', http_client=conn)
        
        self.assertRaises(HTTPError,l.find_assetfolder,'/path/to/my/asset_folder')
            
        # self.assertEqual(ex.exception.response.status, 500)
        # self.assertEqual(ex.exception.url, "http://localhost:80/gnm_asset_folder/lookup?path=%2Fpath%2Fto%2Fmy%2Fasset_folder")