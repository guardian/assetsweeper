from Queue import PriorityQueue
from mutex import mutex
from time import sleep, time

class mutex_protected(object):
    def __init__(self, mutex):
        self._mutex = mutex
        
    def __call__(self, f):
        def wrapped_function(*args):
            def callout(args):
                try:
                    f(*args)
                finally:
                    self._mutex.unlock()
            self._mutex.lock(callout,args)
        return wrapped_function
    
    
class ThreadPool(object):
    _mutex = mutex()
    scale_down_timeout = 0.5    #wait on each thread this long when finding one that has terminated
    scale_down_longtimeout = 30
    scale_down_wait = 1         #wait this number of seconds between checking for terminating threads
    
    class ScaleDownError(StandardError):
        pass
    
    def __init__(self, thread_cls, initial_size=1, min_size=0, max_size=10, *args,**kwargs):
        """
        initialise a new thread pool
        :param thread_cls:  Thread subclass to manage. We expect a constructor that takes a Queue as the first parameter.
        A None value pushed to the queue indicates that the thread should terminate.
        :param initial_size: initial size of the pool
        :param *args: positional arguments for thread constructor
        :param **kwargs: keyword arguments for thread constructor
        """
        self._thread_list = []
        self._thread_cls = thread_cls
        self._thread_args = args
        self._thread_kwargs = kwargs
        self.size = initial_size
        self.queue = PriorityQueue()
        self.min_size = min_size
        self.max_size = max_size
        if initial_size<min_size or initial_size>max_size:
            raise ValueError("initial_size must be between min size and max size")
        
        self.startup_threads(self.size)
        
    def put_queue(self, item, priority=10):
        """
        Add an item to the work queue
        :param item:  item. this should be thread-safe or immutable
        :param priority: integer, lower number means higher priority. Priority 0 is reserved.
        :return: None
        """
        if priority<1:
            raise ValueError("Priority 0 is reserved")
        self.queue.put((priority, item))
        
    def _new_thread(self):
        t = self._thread_cls(self.queue, *self._thread_args, **self._thread_kwargs)
        t.start()
        return t
    
    @mutex_protected(_mutex)
    def startup_threads(self, number):
        for n in range(0,number):
            self._thread_list.append(self._new_thread())
    
    @mutex_protected(_mutex)
    def scale_up(self):
        self._thread_list.append(self._new_thread())
        self.size+=1
        
    @mutex_protected(_mutex)
    def _safe_thread_list_remove(self,t):
        self._thread_list.remove(t)
        
    def scale_down(self, timeout):
        self.queue.put((0, None, )) #make this top priority.
        
        start_time = time()
        while True:
            for t in self._thread_list:
                t.join(self.scale_down_timeout)
                if not t.isAlive():
                    self._safe_thread_list_remove(t)
                    return True
            sleep(self.scale_down_wait)
            if time()-start_time >= timeout:
                raise self.ScaleDownError("No threads terminated in time")
            
    def safe_terminate(self):
        for t in self._thread_list:
            self.put_queue(None, priority=99) #bottom priority, i.e. complete all other work first
        for t in self._thread_list:
            t.join(self.scale_down_longtimeout)
            