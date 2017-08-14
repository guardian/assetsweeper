from __future__ import absolute_import
import unittest
from mock import MagicMock, patch, call
import logging

logging.basicConfig(level=logging.DEBUG)


class FakeConfig(object):
    def value(self, key, noraise=False):
        if key=="start_path":
            return "/path/to/media"
        else:
            raise ValueError(key)


class TestFindFiles(unittest.TestCase):
    """
    tests the find_files module functionality
    """

    def test_find_files(self):
        """
        find files should walk() a directory path and call upsert_file_record for each entry
        :return:
        """
        from asset_folder_importer.database import importer_db
        mock_db = MagicMock(target=importer_db)
        mock_db.upsert_file_record = MagicMock()

        with patch('os.walk',return_value=[('/srv/MediaVolume/Media Production/Assets/WorkingGroup/Commission_Name/user_ProjectName',
                                           [],
                                           ['mediafile1.mxf','mediafile1.xml','mediafile2.mp4'])]):
            with patch('asset_folder_importer.asset_folder_sweeper.find_files.check_mime',return_value=('fake-statinfo','video/something')) as mock_check_mime:
                from asset_folder_importer.asset_folder_sweeper.find_files import find_files
                find_files(FakeConfig(),mock_db)

                mock_db.upsert_file_record.assert_has_calls([
                    call('/srv/MediaVolume/Media Production/Assets/WorkingGroup/Commission_Name/user_ProjectName',"mediafile1.mxf",'fake-statinfo','video/something',asset_folder='WorkingGroup/Commission_Name/user_ProjectName',ignore=False),
                    call('/srv/MediaVolume/Media Production/Assets/WorkingGroup/Commission_Name/user_ProjectName',"mediafile1.xml",'fake-statinfo','video/something',asset_folder='WorkingGroup/Commission_Name/user_ProjectName',ignore=False),
                    call('/srv/MediaVolume/Media Production/Assets/WorkingGroup/Commission_Name/user_ProjectName',"mediafile2.mp4",'fake-statinfo','video/something',asset_folder='WorkingGroup/Commission_Name/user_ProjectName',ignore=False),
                ])

