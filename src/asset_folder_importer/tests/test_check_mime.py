from __future__ import absolute_import
import unittest
import os


class TestCheckMime(unittest.TestCase):
    dbhost = os.environ['DB_HOST'] if 'DB_HOST' in os.environ else 'localhost'
    dbport = os.environ['DB_PORT'] if 'DB_PORT' in os.environ else "5432"
    dbuser = os.environ['DB_USER'] if 'DB_USER' in os.environ else 'asset_folder_importer'
    dbpass = os.environ['DB_PASS'] if 'DB_PASS' in os.environ else 'assetimporter'
    dbname = os.environ['DB_NAME'] if 'DB_NAME' in os.environ else 'assetimporter'

    def test_check_mime(self):
        from asset_folder_importer.asset_folder_sweeper.find_files import check_mime
        from asset_folder_importer.database import importer_db

        __version__ = 'database_test'

        db = importer_db(__version__,hostname=self.dbhost,port=self.dbport,username=self.dbuser,
                         password=self.dbpass,dbname=self.dbname)

        filepath = "/etc/hosts"

        (statinfo, mimetype) = check_mime(filepath, db)

        self.assertEqual(mimetype, "text/plain")
        self.assertNotEqual(statinfo, None)