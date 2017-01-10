__author__ = 'dave'

import unittest
import logging

class TestDatabase(unittest.TestCase):
    def __init__(self,*args,**kwargs):
        super(TestDatabase,self).__init__(*args,**kwargs)
        self._cached_id = None

    def test__has_column(self):

        import sys
        sys.path.insert(0, '../src/')

        from asset_folder_importer.database import importer_db
        from asset_folder_importer.config import configfile

        cfg=configfile("/etc/asset_folder_importer.cfg")

        __version__ = 'asset_folder_sweeper $Rev$ $LastChangedDate$'

        db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))

        self.assertEqual(db._has_column('system','id'),True)

        self.assertEqual(db._has_column('files','filepath'),True)

        self.assertEqual(db._has_column('files','hamster'),False)

    def test__has_table(self):

        import sys
        sys.path.insert(0, '../src/')

        from asset_folder_importer.database import importer_db
        from asset_folder_importer.config import configfile

        cfg=configfile("/etc/asset_folder_importer.cfg")

        __version__ = 'asset_folder_sweeper $Rev$ $LastChangedDate$'

        db = importer_db(__version__,hostname=cfg.value('database_host'),port=cfg.value('database_port'),username=cfg.value('database_user'),password=cfg.value('database_password'))

        self.assertEqual(db._has_table('system'),True)

        self.assertEqual(db._has_table('files'),True)

        self.assertEqual(db._has_table('hamster'),False)