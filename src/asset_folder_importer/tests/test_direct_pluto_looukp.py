from __future__ import absolute_import
import unittest
import mock
import logging
import json
import requests

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

        response_success = mock.MagicMock(requests.models.Response)
        response_success.status_code = 200
        response_success.text = self.success_data

        #test successful lookup
        with mock.patch("requests.get", return_value=response_success):
            l = DirectPlutoLookup(logger=logger)
            result = l.lookup('/path/to/something/')
            self.assertEqual(result,'VX-123')

        #test unsuccessful lookup
        response_failure = mock.MagicMock(requests.models.Response)
        response_failure.status_code = 404
        response_failure.text = self.notfound_data

        with mock.patch("requests.get", return_value=response_failure):
            l = DirectPlutoLookup()
            result = l.lookup('/path/to/something')
            self.assertEqual(result,None)

    def test_retry(self):
        from asset_folder_importer.fix_unattached_media.direct_pluto_lookup import DirectPlutoLookup

        response = mock.MagicMock(requests.models.Response)
        response.status_code = 504
        response.text = ""

        with mock.patch("requests.get", return_value=response):
            l = DirectPlutoLookup(max_retries=2,retry_delay=1)
            result = l.lookup('/path/to/something')
            self.assertEqual(result, None)