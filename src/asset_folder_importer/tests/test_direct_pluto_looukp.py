from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging
import httplib
import json


class TestDirectPlutoLookup(unittest.TestCase):
    fake_host = 'localhost'
    fake_port = 8080
    fake_user = 'username'
    fake_passwd = 'password'
    
    success_data=json.dumps({
        'status': 'ok',
        'path': '/path/to/something',
        'project': 'VX-123'
    })
    
    notfound_data=json.dumps({
        'status': 'notfound'
    })
    
    class MockedResponse(object):
        def __init__(self, status_code, content, reason=""):
            self.status = status_code
            self.body = content
            self.reason = reason
        
        def read(self):
            return self.body
    
    def test_lookup(self):
        from asset_folder_importer.fix_unattached_media.direct_pluto_lookup import DirectPlutoLookup
        logger = logging.getLogger("test")
        logger.debug=mock.MagicMock()
        conn = httplib.HTTPConnection(self.fake_host,self.fake_port)
        conn.request = mock.MagicMock()
        conn.getresponse = mock.MagicMock(return_value=self.MockedResponse(200,self.success_data))
        
        #test successful lookup
        l = DirectPlutoLookup(conn=conn,logger=logger)
        result = l.lookup('/path/to/something/')
        conn.request.assert_called_once()
        conn.getresponse.assert_called_once()
        #ensure that the trailing / is stripped
        logger.debug.assert_called_with("Looking up URL /gnm_asset_folder/lookup?path=%2Fpath%2Fto%2Fsomething")
        self.assertEqual(result,'VX-123')

        #test unsuccessful lookup
        conn = httplib.HTTPConnection(self.fake_host, self.fake_port)
        conn.request = mock.MagicMock()
        conn.getresponse = mock.MagicMock(return_value=self.MockedResponse(404, self.notfound_data))
        
        l = DirectPlutoLookup(conn=conn)
        result = l.lookup('/path/to/something')
        conn.request.assert_called_once()
        conn.getresponse.assert_called_once()
        self.assertEqual(result,None)
        
    def test_retry(self):
        from asset_folder_importer.fix_unattached_media.direct_pluto_lookup import DirectPlutoLookup
        
        conn = httplib.HTTPConnection(self.fake_host, self.fake_port)
        conn.request = mock.MagicMock()
        conn.getresponse = mock.MagicMock(return_value=self.MockedResponse(504, ""))
    
        l = DirectPlutoLookup(conn=conn,max_retries=2,retry_delay=1)
        result = l.lookup('/path/to/something')
        conn.request.assert_called()
        self.assertEqual(conn.request.call_count, 2)
        conn.getresponse.assert_called()
        self.assertEqual(conn.request.call_count,2)
        self.assertEqual(result, None)