# coding=utf-8
import unittest2
from mock import MagicMock, patch
import logging

logging.basicConfig(level=logging.DEBUG)

class TestProcessPremiereProject(unittest2.TestCase):
    class FakeConfig(object):
        def __init__(self):
            self.content = {
                'vs_host': 'host',
                'vs_port': 8080,
                'vs_user': 'fred',
                'vs_passwd': 'smith'
            }

        def value(self, key):
            return getattr(self.content,key,None)

    def test_load_correct_collection(self):
        """
        process_premiere_project should load VS collection with the right ID given from the project name
        :return:
        """
        from asset_folder_importer.database import importer_db
        from gnmvidispine.vs_collection import VSCollection
        mock_database = MagicMock(target=importer_db)

        #with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection') as mock_coll:
        mock_coll_instance = MagicMock(target=VSCollection)

        with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection', return_value=mock_coll_instance):
            with patch('asset_folder_importer.premiere_get_referenced_media.processor.PremiereProject') as mock_proj:
                mock_proj.getReferencedMedia = MagicMock(return_value=['/Volumes/Internet Downloads/WRONG FILE.mov'])
                from asset_folder_importer.premiere_get_referenced_media.processor import process_premiere_project
                process_premiere_project("/fakeproject/VX-446.prproj", None, db=mock_database, cfg=self.FakeConfig())
                mock_coll_instance.populate.assert_called_with("VX-446")

    def test_notify_wrongpath(self):
        """
        process_premiere_project should update project record with any non-SAN media paths
        :return:
        """
        from asset_folder_importer.database import importer_db
        from gnmvidispine.vs_collection import VSCollection
        from gnmvidispine.vidispine_api import VSNotFound
        from gnmvidispine.vs_item import VSItem
        from asset_folder_importer.premiere_get_referenced_media.PremiereProject import PremiereProject
        mock_database = MagicMock(target=importer_db)

        #with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection') as mock_coll:
        mock_coll_instance = MagicMock(target=VSCollection)
        mock_proj_instance = MagicMock(target=PremiereProject)
        mock_item_instance = MagicMock(target=VSItem)
        mock_proj_instance.getReferencedMedia = MagicMock(return_value=['/Volumes/Internet Downloads/WRONG FILE.mov'])
        mock_coll_instance.get = MagicMock(return_value=None)
        with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection', return_value=mock_coll_instance) as mock_coll:
            with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSItem', return_value=mock_item_instance):
                with patch('asset_folder_importer.premiere_get_referenced_media.processor.PremiereProject', return_value=mock_proj_instance) as mock_proj:
                    with patch('asset_folder_importer.premiere_get_referenced_media.processor.process_premiere_fileref',side_effect=VSNotFound()):
                        from asset_folder_importer.premiere_get_referenced_media.processor import process_premiere_project

                        process_premiere_project("/fakeproject/VX-446.prproj", None, db=mock_database, cfg=self.FakeConfig())
                        mock_coll_instance.set_metadata.assert_called_with({'gnm_project_invalid_media_paths': '/Volumes/Internet Downloads/WRONG FILE.mov'},mode="add")

    def test_filepath_unicode(self):
        """
        process_premiere_project should be able to cope with a non-ASCII character in the file path
        :return:
        """
        from asset_folder_importer.database import importer_db
        from gnmvidispine.vs_collection import VSCollection
        from gnmvidispine.vidispine_api import VSNotFound
        from gnmvidispine.vs_item import VSItem
        from asset_folder_importer.premiere_get_referenced_media.PremiereProject import PremiereProject
        mock_database = MagicMock(target=importer_db)

        #with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection') as mock_coll:
        mock_coll_instance = MagicMock(target=VSCollection)
        mock_proj_instance = MagicMock(target=PremiereProject)
        mock_item_instance = MagicMock(target=VSItem)
        mock_proj_instance.getReferencedMedia = MagicMock(return_value=['/Volumes/Multimedia2/Media Production/Assets/ES_Mastermind - Johannes Bornlöf.mp3'])
        with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection', return_value=mock_coll_instance) as mock_coll:
            with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSItem', return_value=mock_item_instance):
                with patch('asset_folder_importer.premiere_get_referenced_media.processor.PremiereProject', return_value=mock_proj_instance) as mock_proj:
                    with patch('asset_folder_importer.premiere_get_referenced_media.processor.process_premiere_fileref',side_effect=VSNotFound()):
                        from asset_folder_importer.premiere_get_referenced_media.processor import process_premiere_project

                        self.assertEqual(process_premiere_project("/fakeproject/VX-446.prproj", None, db=mock_database, cfg=self.FakeConfig()), (1, 0, 0))

    def test_filepath_ascii(self):
        """
        process_premiere_project should be able to cope with a file path with only ASCII characters
        :return:
        """
        from asset_folder_importer.database import importer_db
        from gnmvidispine.vs_collection import VSCollection
        from gnmvidispine.vidispine_api import VSNotFound
        from gnmvidispine.vs_item import VSItem
        from asset_folder_importer.premiere_get_referenced_media.PremiereProject import PremiereProject
        mock_database = MagicMock(target=importer_db)

        #with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection') as mock_coll:
        mock_coll_instance = MagicMock(target=VSCollection)
        mock_proj_instance = MagicMock(target=PremiereProject)
        mock_item_instance = MagicMock(target=VSItem)
        mock_proj_instance.getReferencedMedia = MagicMock(return_value=['/Volumes/Multimedia2/Media Production/Assets/ASCII.mp3'])
        with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSCollection', return_value=mock_coll_instance) as mock_coll:
            with patch('asset_folder_importer.premiere_get_referenced_media.processor.VSItem', return_value=mock_item_instance):
                with patch('asset_folder_importer.premiere_get_referenced_media.processor.PremiereProject', return_value=mock_proj_instance) as mock_proj:
                    with patch('asset_folder_importer.premiere_get_referenced_media.processor.process_premiere_fileref',side_effect=VSNotFound()):
                        from asset_folder_importer.premiere_get_referenced_media.processor import process_premiere_project

                        self.assertEqual(process_premiere_project("/fakeproject/VX-446.prproj", None, db=mock_database, cfg=self.FakeConfig()), (1, 0, 0))

