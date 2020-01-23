__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'

#This module is a custom "handler" for the standard library 'logging'. By default, it will output warning and error messages
#to the asset importer database
#You are expected to have initialised a database connection using asset_folder_importer.database first and then pass this into
#the constructor
#Like this:
#
# from asset_folder_importer.database import importer_db
#
# db = importer_db(__version__,host="host",port="port",user="user",paswd="pass")
# handler = AssetImporterLoggingHandler(db) #<--raises an error if the argument is not a reference to importer_db
# logging.addHandler(handler)


import logging
from . import database


class AssetImporterLoggingHandler(logging.Handler, object): #second inheritance is necessary to avoid TypeError on the super() call below
    def __init__(self,dbref,level=logging.WARN):
        super(AssetImporterLoggingHandler,self).__init__(level=level)

        if not isinstance(dbref,database.importer_db):
            raise TypeError("AssetImporterLoggingHandler - Not passed an instance of asset importer database. Cannot continue.")

        self.dbref = dbref

    def emit(self, record):
        db = self.dbref

        #pprint(record.__dict__)
        #print "AssetImporterLoggingHandler::emit: level {0} message {1}".format(record.levelname,record.msg)
        paramname = record.levelname.lower()
        db.insert_sysparam(paramname,record.msg)