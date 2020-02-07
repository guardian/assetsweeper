__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = '$Rev$ $LastChangedDate$'

from asset_folder_importer.database import *
from datetime import datetime
import xml.etree.ElementTree as ET
import os
import logging

# Configurable parameters
LOGFORMAT = '%(asctime)-15s - %(levelname)s - %(message)s'
main_log_level = logging.DEBUG
logfile = "/var/log/plutoscripts/prelude_importer.log"
#End configurable parameters

if logfile is not None:
    logging.basicConfig(filename=logfile, format=LOGFORMAT, level=main_log_level)
else:
    logging.basicConfig(format=LOGFORMAT, level=main_log_level)


class NotPreludeProjectException(Exception):
    pass

class InvalidXMLException(Exception):
    pass

class preludeclip:
    def __init__(self,data):
        self.dataContent=data

    def assert_elements(self,elem_list):
        for i in elem_list:
            if not i in self.dataContent:
                self.dataContent[i]=""

    def match_fileref(self,db):
        if not 'FilePath' in self.dataContent:
            return None

        fileref=db.fileId(self.dataContent['FilePath'])
        if fileref is not None:
            logging.debug("Data going into update_prelude_clip_fileref: database_id = {0} fileref = {1}".format(self.database_id,fileref))
            db.update_prelude_clip_fileref(self.database_id,fileref)

    def commit(self,db,projectref):
        self.assert_elements(['AssetName','AssetRelinkSkipped','AssetType','ClassID','CreatedDate','DropFrame','Duration','FilePath','FrameRate',
                              'ImportDate','ParentClassID','StartTime'])

        self.database_id=db.upsert_prelude_clip(
            project_ref=projectref,
            asset_name=self.dataContent['AssetName'].encode('utf-8'),
            asset_relink_skipped=self.dataContent['AssetRelinkSkipped'],
            asset_type=self.dataContent['AssetType'],
            uuid=self.dataContent['ClassID'],
            created_date=datetime.strptime(self.dataContent['CreatedDate'],'%m/%d/%y, %H:%M:%S'),
            drop_frame=self.dataContent['DropFrame'],
            duration=self.dataContent['Duration'],
            file_path=self.dataContent['FilePath'].encode('utf-8'),
            frame_rate=self.dataContent['FrameRate'],
            import_date=datetime.strptime(self.dataContent['ImportDate'],'%Y-%m-%d %H:%M:%S'),
            parent_uuid=self.dataContent['ParentClassID'],
            start_time=self.dataContent['StartTime'],
            )

        self.match_fileref(db)
    def dump(self):
        print("Prelude clip:")
        for k,v in list(self.dataContent.items()):
            print("\t%s: %s" % (k,v))

class preludeimporter:
    def __init__(self,db,prelude_path):
        self.project_file_path=os.path.dirname(prelude_path)
        self.project_file_name=os.path.basename(prelude_path)
        self.uuid=""
        self.version=""

        self.clipList=[]

        try:
            data=ET.parse(prelude_path)
        #the xml.etree.ElementTree.ParseError exception was added in Python 2.7 so can't use that here.
            if data is None:
                raise InvalidXMLException()
        except Exception as e:
            #note in the database anyway, then bounce the exception up the chain
            self.projectid=db.upsert_prelude_project(path=self.project_file_path,
                                                           filename=self.project_file_name,
                                                           version="(invalid xml)")
            raise InvalidXMLException(e)

        root_element=data.getroot()

        if root_element.tag != "Project":
            msg = "%s does not appear to be a Prelude project xml (no <Project> root node)"
            raise NotPreludeProjectException(msg)

        if 'ClassID' in root_element.attrib:
            self.uuid=root_element.attrib['ClassID']
        if 'version' in root_element.attrib:
            self.version=root_element.attrib['version']

        self.projectid=db.upsert_prelude_project(path=self.project_file_path,
                                         filename=self.project_file_name,
                                         uuid=self.uuid,
                                         version=self.version)

        for child_element in root_element:
            if child_element.tag == "MasterClip":
                clip=preludeclip(child_element.attrib)
                #clip.dump()
                logging.debug("Data going into clip.commit: projectid = {0}".format(self.projectid))
                clip.commit(db,self.projectid)
                self.clipList.append(clip)

        db.update_project_nclips(self.nclips(), projectid=self.projectid)

    def nclips(self):
        return len(self.clipList)

    def clips(self):
        for c in self.clipList:
            yield c

    def dump(self):
        print("Prelude project at {path}/{filename}, version {ver} with {nclips} clips".format(
            path=self.project_file_path,
            filename=self.project_file_name,
            ver=self.version,
            nclips=self.nclips()
        ))
        logging.info("Prelude project at {path}/{filename}, version {ver} with {nclips} clips".format(
            path=self.project_file_path,
            filename=self.project_file_name,
            ver=self.version,
            nclips=self.nclips()
        ))
        print("Database ID is %s, UUID is %s" % (self.projectid,self.uuid))
        logging.info("Database ID is %s, UUID is %s" % (self.projectid,self.uuid))
