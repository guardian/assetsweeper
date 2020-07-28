from __future__ import absolute_import
import unittest
from queue import Queue
import mock

import logging


class TestUpdateVsThread(unittest.TestCase):
    def _fake_config_get(self, key):
        if key=="vs_masters_storage":
            return "VX-2"
        else:
            return "x"

    def test_setup(self):
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config, timeout=5)

        self.assertEqual(t.config, fake_config)
        self.assertEqual(t._q, test_queue)
        fake_storage.populate.assert_called_once_with("VX-2")

    def test_process_item(self):
        """
        process_item should look up an item on the provided VS storage and tell VS to update its state to 'missing'
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(return_value=fake_file)

        file_data = {
            'filepath': "/path/to/my/assets",
            'filename': "asset.mxf"
        }

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)
            t.check_should_update = mock.MagicMock()
        t.process_item(file_data)
        t.check_should_update.assert_not_called() #if no indication in file_data don't check for update
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")
        fake_file.setState.assert_called_once_with("MISSING")

    def test_process_item_notfound(self):
        """
        process_item should skip over an item that is not found by VS, not logging to Sentry
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile, VSNotFound

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(side_effect=VSNotFound())

        file_data = {
            'filepath': "/path/to/my/assets",
            'filename': "asset.mxf"
        }

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)
        t.process_item(file_data)
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")
        fake_file.setState.assert_not_called()

    def test_process_item_notneeded(self):
        """
        if item check indicates no update needed we should move on
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile, VSNotFound

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(return_value=fake_file)

        file_data = {
            'filepath': "/path/to/my/assets",
            'filename': "asset.mxf",
            'should_verify': 1
        }

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)
            t.check_should_update = mock.MagicMock(side_effect=UpdateVsThread.NoUpdateNeeded)

        t.process_item(file_data)
        t.check_should_update.assert_called_once_with("/path/to/my/assets/asset.mxf")
        fake_file.setState.assert_not_called()

    def test_process_item_vsexception(self):
        """
        process_item should log any other vidispine exception
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile
        from gnmvidispine.vidispine_api import VSBadRequest

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(side_effect=VSBadRequest())

        file_data = {
            'filepath': "/path/to/my/assets",
            'filename': "asset.mxf"
        }

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)
        t.process_item(file_data)
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")
        fake_file.setState.assert_not_called()

    def test_should_update(self):
        """
        check_should_update should return the fileref if the loaded file state is not 'MISSING'
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)
        fake_file.state = 'ONLINE'

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(return_value=fake_file)

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)

        result = t.check_should_update("/path/to/my/assets/asset.mxf")
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")
        self.assertEqual(result, fake_file)

    def test_should_update_missing(self):
        """
        check_should_update should raise NoUpdateNeeded if the file is MISSING
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)
        fake_file.state = 'MISSING'

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(return_value=fake_file)

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)

        with self.assertRaises(UpdateVsThread.NoUpdateNeeded):
            result = t.check_should_update("/path/to/my/assets/asset.mxf")
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")

    def test_should_update_lost(self):
        """
        check_should_update should raise NoUpdateNeeded if the file is LOST
        :return:
        """
        from asset_folder_importer.asset_folder_verify_files.update_vs_thread import UpdateVsThread
        from asset_folder_importer.config import configfile
        from gnmvidispine.vs_storage import VSStorage, VSFile

        test_queue = Queue()
        fake_config = mock.MagicMock(target=configfile)
        fake_config.value = mock.MagicMock(side_effect=self._fake_config_get)
        fake_file = mock.MagicMock(target=VSFile)
        fake_file.state = 'LOST'

        fake_storage = mock.MagicMock(target=VSStorage)
        fake_storage.populate = mock.MagicMock()
        fake_storage.fileForPath = mock.MagicMock(return_value=fake_file)

        with mock.patch('gnmvidispine.vs_storage.VSStorage', return_value=fake_storage):
            t = UpdateVsThread(test_queue, config=fake_config)

        with self.assertRaises(UpdateVsThread.NoUpdateNeeded):
            result = t.check_should_update("/path/to/my/assets/asset.mxf")
        fake_storage.fileForPath.assert_called_once_with("/path/to/my/assets/asset.mxf")