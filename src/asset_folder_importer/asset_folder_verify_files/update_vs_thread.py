import threading
import logging
from mock import MagicMock
import raven
import traceback
import os.path
from gnmvidispine.vidispine_api import VSException, VSNotFound

logger = logging.getLogger(__name__)


class UpdateVsThread(threading.Thread):
    """
    A thread that tells Vidispine that a file is now missing
    """
    def __init__(self, jobqueue, *args, **kwargs):
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage
        if not 'config' in kwargs:
            raise ValueError("You need to pass config= to UpdateVsThread")
        if not isinstance(kwargs['config'], configfile) and not isinstance(kwargs['config'],MagicMock):
            raise ValueError("config= is not an asset importer config object")

        super(UpdateVsThread, self).__init__()
        self._q = jobqueue

        self.config = kwargs['config']
        self.timeout=kwargs.get('timeout',3600)
        self._storage = VSStorage(host=self.config.value("vs_host"),
                                  port=self.config.value("vs_port"),
                                  user=self.config.value("vs_user"),
                                  passwd=self.config.value("vs_password"))
        self._storage.populate(self.config.value("vs_masters_storage"))
        self._sentry_context = {}

        try:
            self._raven_client = raven.Client(self.config.value("sentry_dsn"))
        except Exception as e:
            logger.error("Could not initialise Raven: {0}. Errors will not be logged to Sentry.".format(str(e)))
            self._raven_client = None

    def update_sentry_context(self, data):
        """
        safe-set for sentry context. No-op if sentry client is not set up.
        :param data: dictionary to set
        :return: True if set, otherwise False
        """
        self._sentry_context.update(data)

        if self._raven_client is not None:
            self._raven_client.extra_context(self._sentry_context)
            return True
        else:
            return False

    def clear_sentry_context(self):
        """
        safe-clear for sentry context. No-op if sentry client is not set up.
        :return:
        """
        self._sentry_context = {}

        if self._raven_client is not None:
            self._raven_client.extra_context({})
            return True
        else:
            return False

    class NoUpdateNeeded(StandardError):
        pass

    def check_should_update(self, filepath):
        """
        checks if the current file status does not need updating. Raises self.NoUpdateNeeded if it's not needed.
        :param filepath: path of file to check
        :return: VSFile object for 'filepath'
        """
        fileref = self._storage.fileForPath(filepath)
        if fileref.state=='MISSING' or fileref.state=='LOST':
            raise self.NoUpdateNeeded(filepath)
        return fileref

    def process_item(self, item):
        """
        notify Vidispine about a missing file
        :param item: file info hash, as returned by db.files()
        :return:
        """
        filepath = os.path.join(item['filepath'], item['filename'])

        try:
            if 'should_verify' in item:
                fileref = self.check_should_update(filepath)
            else:
                fileref = self._storage.fileForPath(filepath)
            logger.info("{0} ({1}): updating state from {2} to MISSING".format(filepath, fileref.name, fileref.state))
            fileref.setState('MISSING')
        except self.NoUpdateNeeded:
            logger.debug("{0}: no update needed".format(filepath))
        except VSNotFound as e:
            logger.warning("Deleted file {0} not found in Vidispine".format(filepath))
        except VSException as e:
            logger.error("Vidispine error updating {0} to missing state".format(filepath))
            if self._raven_client is not None:
                self._raven_client.captureException()

    def run(self):
        """
        thread main process. Receive message from queue and dispatch. Exit if told to.
        :return:
        """
        while True:
            (prio, item) = self._q.get(timeout=self.timeout)
            if item is None:
                logger.warning("Received null, terminating thread")
                return
            try:
                self.update_sentry_context({"item": item})
                self.process_item(item)
                self.clear_sentry_context()
            except Exception as e:
                if self._raven_client is not None:
                    self._raven_client.captureException()
                logger.error(traceback.format_exc())
                self.clear_sentry_context()