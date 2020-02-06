
import unittest
import os
import threading
import mock


class TestThread(threading.Thread):
    def __init__(self, input_q, keywordarg=None, *args, **kwargs):
        super(TestThread, self).__init__(*args, **kwargs)
        self._queue = input_q
        self.keywordarg = keywordarg
        self.outputvalue = None
        
    def processor(self, item):
        self.outputvalue = item
    
    def run(self):
        from time import sleep
        
        while True:
            (prio, item) = self._queue.get()
            if item is None: break
            self.processor(item)
            # simulate processing with a 10 second wait
            sleep(5)
            
            
class TestThreadpool(unittest.TestCase):
    from asset_folder_importer.threadpool import ThreadPool
                  
    def test_new_threadpool(self):
        """
        test that a thread pool starts up correctly, and safely terminate
        :return:
        """
        pool = self.ThreadPool(TestThread,initial_size=1,keywordarg="keywordstring")
        
        self.assertEqual(threading.activeCount(),2)
        pool.safe_terminate()
        
    def test_scaleup(self):
        """
        test that a thread pool will scale up properly
        :return:
        """
        pool = self.ThreadPool(TestThread, initial_size=1, keywordarg="keywordstring")
    
        try:
            self.assertEqual(threading.activeCount(), 2)
            pool.scale_up()
            self.assertEqual(threading.activeCount(), 3)
            pool.scale_up()
            self.assertEqual(threading.activeCount(), 4)
        finally:
            pool.safe_terminate()
        
    def test_scaledown(self):
        """
        test that a thread pool will scale down properly
        :return:
        """
        pool = self.ThreadPool(TestThread, initial_size=10, keywordarg="keywordstring")
        
        try:
            self.assertEqual(threading.activeCount(), 11)
            pool.scale_down(timeout=1)
            self.assertEqual(threading.activeCount(), 10)
            pool.scale_down(timeout=1)
            self.assertEqual(threading.activeCount(), 9)
            pool.scale_down(timeout=1)
            self.assertEqual(threading.activeCount(), 8)
            pool.scale_down(timeout=1)
            self.assertEqual(threading.activeCount(), 7)
            pool.scale_down(timeout=1)
        finally:
            pool.safe_terminate()

    def test_put_queue(self):
        """
        test that the thread pool object exposes a queue properly
        :return:
        """
        from time import sleep
        testitem = {
            'a': 'dictionary'
        }
        pool = None
        try:
            pool = self.ThreadPool(TestThread,initial_size=1, keywordarg="string")
            pool.put_queue(testitem)
            
            sleep(1)
            thread_ref = pool._thread_list[0]   #use internal thread ref to test with
            self.assertEqual(thread_ref.outputvalue,testitem)
        finally:
            if pool is not None: pool.safe_terminate()