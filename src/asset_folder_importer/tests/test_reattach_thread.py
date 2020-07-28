from __future__ import absolute_import
import unittest
import os
import threading
import mock
import logging


class TestReattachThread(unittest.TestCase):
    def test_runloop_timeout(self):
        from asset_folder_importer.fix_unattached_media import reattach_thread
        from queue import PriorityQueue
        q = PriorityQueue()
        
        logger = logging.getLogger("test_runloop")
        logger.debug = mock.MagicMock()
        logger.error = mock.MagicMock()
        logger.info = mock.MagicMock()
        logger.warning = mock.MagicMock()
        
        rat = reattach_thread.ReattachThread(q,options=None,timeout=2,logger=logger)
        
        rat.run()
        
        logger.error.assert_called_with("Input queue timed out, exiting.")
        logger.info.assert_called_with("Reattach thread terminating")

    def test_runloop_execute(self):
        from asset_folder_importer.fix_unattached_media import reattach_thread
        from queue import PriorityQueue
        
        q = PriorityQueue()

        logger = logging.getLogger("test_runloop")
        logger.debug = mock.MagicMock()
        logger.error = mock.MagicMock()
        logger.info = mock.MagicMock()
        logger.warning = mock.MagicMock()
        
        rat = reattach_thread.ReattachThread(q, options=None, timeout=2,
                                             logger=logger, should_raise=True)
        q.put((1, {'itemid': 'KP-1234', 'collectionid': 'KP-5678'}))
        rat.reattach = mock.MagicMock()
        
        rat.run()

        rat.reattach.assert_called_with('KP-1234', 'KP-5678')
        logger.error.assert_called_with("Input queue timed out, exiting.")
        logger.info.assert_called_with("Reattach thread terminating")