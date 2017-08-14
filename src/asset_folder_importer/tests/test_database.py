__author__ = 'dave'

import unittest
import logging
import os
from asset_folder_importer.database import importer_db

__version__ = 'database_test'


class TestDatabase(unittest.TestCase):
    dbhost = os.environ['DB_HOST'] if 'DB_HOST' in os.environ else 'localhost'
    dbport = os.environ['DB_PORT'] if 'DB_PORT' in os.environ else "5432"
    dbuser = os.environ['DB_USER'] if 'DB_USER' in os.environ else 'asset_folder_importer'
    dbpass = os.environ['DB_PASS'] if 'DB_PASS' in os.environ else 'assetimporter'
    dbname = os.environ['DB_NAME'] if 'DB_NAME' in os.environ else 'asset_folder_importer'
    
    def __init__(self,*args,**kwargs):
        super(TestDatabase,self).__init__(*args,**kwargs)
        self._cached_id = None

    def test__has_column(self):
        __version__ = 'database_test'

        db = importer_db(__version__,hostname=self.dbhost,port=self.dbport,username=self.dbuser,
                         password=self.dbpass,dbname=self.dbname)

        self.assertEqual(db._has_column('system','id'),True)
        self.assertEqual(db._has_column('files','filepath'),True)
        self.assertEqual(db._has_column('files','hamster'),False)

    def test__has_table(self):

        db = importer_db(__version__, hostname=self.dbhost, port=self.dbport, username=self.dbuser,
                         password=self.dbpass, dbname=self.dbname)

        self.assertEqual(db._has_table('system'),True)
        self.assertEqual(db._has_table('files'),True)
        self.assertEqual(db._has_table('hamster'),False)

    def test__insertfile(self):
        """
        test that we can insert a new file record and retrieve it again
        :return:
        """
        import os
        __version__ = 'database_test'

        print self.dbhost
        print self.dbport
        print self.dbuser
        print self.dbpass
        db = importer_db(__version__, hostname=self.dbhost, port=self.dbport, username=self.dbuser,
                         password=self.dbpass, dbname=self.dbname)
        db.upsert_file_record("/test/path/to","testfile",os.stat(__file__),"test/plain")
        db.commit()

        result = db.fileId("/test/path/to/testfile")
        self.assertIsNotNone(result)

    def test__update_file_assetfolder(self):
        """
        test that we can add an asset folder to a file record
        :return:
        """
        db = importer_db(__version__, hostname=self.dbhost, port=self.dbport, username=self.dbuser,
                         password=self.dbpass, dbname=self.dbname)
        db.upsert_file_record("/test/path/to", "testfile",os.stat(__file__),"test/plain")
        db.check_schema_23()

        result = db.fileId("/test/path/to/testfile")
        self.assertIsNotNone(result)

        db.update_file_assetfolder(result,"WorkingGroup/Commission_Name/Project",should_commit=True)

        result = db.fileRecord("/test/path/to/testfile")
        self.assertDictContainsSubset({'asset_folder': "WorkingGroup/Commission_Name/Project"}, result)