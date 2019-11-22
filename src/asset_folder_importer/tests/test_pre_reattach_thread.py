
import unittest
import os
import threading
import mock
import logging
import http.client
import json
from queue import PriorityQueue


class FakeConfig(object):
    def value(self, key):
        if key.endswith('port'):
            return 80
        return 'test'
    
    
class TestPreReattachThread(unittest.TestCase):
    def test_find_collection_id(self):
        from asset_folder_importer.fix_unattached_media.pre_reattach_thread import PreReattachThread
        inq = PriorityQueue()
        outq = PriorityQueue()
        
        t = PreReattachThread(inq,outq,options=None,config=FakeConfig())

        with mock.patch('asset_folder_importer.fix_unattached_media.collection_lookup.CollectionLookup.find_in_vs',
                        return_value='VX-123'
                        ) as cm:
            value = t.find_collection_id('test_workgroup','test_commission', 'user_name_project_name_here')
            self.assertEqual(value,'VX-123')
            #if we call again it should be cached, so the underlying call should not be made
            value = t.find_collection_id('test_workgroup', 'test_commission', 'user_name_project_name_here')
            self.assertEqual(value, 'VX-123')
            
        cm.assert_called_once_with({
            'project': 'user_name_project_name_here'
        })
        
    def test_process(self):
        from asset_folder_importer.fix_unattached_media.pre_reattach_thread import PreReattachThread, InvalidLocation, NoCollectionFound
        from asset_folder_importer.fix_unattached_media.direct_pluto_lookup import DirectPlutoLookup
        inq = PriorityQueue()
        outq = PriorityQueue()
    
        l = DirectPlutoLookup()
        l.lookup=mock.MagicMock(return_value=None)
        t = PreReattachThread(inq, outq, options=None, config=FakeConfig(), pluto_lookup=l)
        
        t.find_collection_id = mock.MagicMock(return_value='VX-123')
        t._outq.put = mock.MagicMock()
        
        #a valid project should get put onto the output queue
        t.process('VX-456','/srv/Multimedia2/Media Production/Assets/workinggroup_name/commission_name/user_name_projects_stuff_here')
        l.lookup.assert_called_once()
        t.find_collection_id.assert_called_once_with('workinggroup_name','commission_name','user_name_projects_stuff_here')
        t._outq.put.assert_called_once_with({'itemid': 'VX-456', 'collectionid': 'VX-123'},priority=10)
        
        t.find_collection_id.reset_mock()
        l.lookup.reset_mock()
        t._outq.put.reset_mock()
        
        #an invalid data path should give an exception
        def testcall():
            t.process('VX-456', '/Downloads/Internet Downloads/some/path/to/file.mov')
        l.lookup.assert_not_called()
        self.assertRaises(InvalidLocation,testcall)
        
        #if a data path is not found, first we try re-adding 's, and if it still does not work raise an exception
        def secondtestcall():
            #t2 = PreReattachThread(inq, outq, options=None, config=FakeConfig())
            t.find_collection_id = mock.MagicMock(return_value=None)
            t.process('VX-456',
                      '/srv/Multimedia2/Media Production/Assets/workinggroup_name/commission_name/user_name_project_s_stuff_here')
            t.find_collection_id.assert_called_with('workinggroup_name', 'commission_name','user_name_project\'s_stuff_here')
            t._outq.put.assert_not_called()
        self.assertRaises(NoCollectionFound, secondtestcall)