#this also requires python-setuptools to be installed
from jinja2 import Environment,PackageLoader
from gnmvidispine.vs_collection import VSCollection
from gnmvidispine.vs_job import VSJob,VSJobFailed
from gnmvidispine.vs_storage import VSStorage
from gnmvidispine.vidispine_api import VSBadRequest,VSNotFound, VSException, HTTPError, VSConflict
from asset_folder_importer.database import importer_db
from asset_folder_importer.xdcam_metadata import XDCAMImporter,InvalidDataError
from pprint import pprint
from time import sleep, time
import traceback
import os
import re
import time
import logging
import threading
from queue import Empty
import asset_folder_importer.externalprovider as externalprovider
from subprocess import Popen,PIPE
from asset_folder_importer.asset_folder_vsingester.exceptions import *
from glob import glob
from asset_folder_importer.pluto.assetfolder import SweeperHTTPError

__version__ = 'asset_folder_vsingester $$'
__scriptname__ = 'asset_folder_vsingester'


class ImportStalled(Exception):
    pass


class ImporterThread(threading.Thread):
    potentialSidecarExtensions = ['.xml', '.xmp', '.meta', '.XML', '.XMP']
    
    def __init__(self, q, storageid, cfg, permission_script="/invalid/permissionscript",
                 graveyard_folder="/tmp", timeout=60, import_timeout=3600, close_file_timeout=300, logger=None, dbconn=None):
        """
        Initialises a new ImporterThread
        :param q: job queue to work from
        :param storageid: Storage ID to import from
        :param cfg: configuration object from config file and commandline
        :param permission_script: location of the suid change-permissions script
        :param graveyard_folder: graveyard folder to move invalid jobs to (defaults to /tmp)
        :param timeout: time to wait for API calls to complete (default: 60s; this is also the loadbalancer timeout)
        :param import_timeout: time to wait for a Vidispine import job before cancelling it as it is stalled (default: 1 hour)
        :param close_file_timeout: time to wait on processing a job before sending vidispine a close-file request (see https://support.vidispine.com/support/tickets/1360) (default: 5mins)
        :param logger: logger object to log to. For testing purposes, really; if None then a new logger will be created. (default: None)
        :param dbconn: database connection. For testing purposes really; if None then a new database connection will be created (default: None)
        """
        super(ImporterThread, self).__init__()
        
        self.templateEnv = Environment(loader=PackageLoader('asset_folder_importer', 'metadata_templates'))
        self.mdTemplate = self.templateEnv.get_template('vsasset.xml')
        self.queue = q
        self.st = VSStorage(host=cfg.value('vs_host'), port=cfg.value('vs_port'), user=cfg.value('vs_user'),
                            passwd=cfg.value('vs_password'))
        if storageid is not None:
            self.st.populate(storageid)
        self.db = dbconn if dbconn is not None else importer_db(__version__, hostname=cfg.value('database_host'),
                                                                port=cfg.value('database_port'),
                                                                username=cfg.value('database_user'),
                                                                password=cfg.value('database_password'))
        self.found = 0
        self.withItems = 0
        self.imported = 0
        self.cfg = cfg
        self.ignored = 0
        self._permissionscript = permission_script
        self.logger = logger if logger is not None else logging.getLogger("importer_thread")
        self._timeout = timeout
        self.graveyard_folder=graveyard_folder
        self._importer_timeout = import_timeout
        self._close_file_timeout = close_file_timeout
        try:
            providers_config_file = self.cfg.value('footage_providers_config', noraise=False)
        except KeyError:
            providers_config_file = '/etc/asset_folder_importer/footage_providers.yml'

        self.providers_list = externalprovider.ExternalProviderList(providers_config_file)
        self.portal_error = False
        
    def get_cubase_data(self, filepath, filename):
        """
        Look to see if we think this media file comes from Cubase
        :param filepath: filepath to investigate
        :param filename: not used
        :return: dictionary of Cubase related metadata if it's in an Audio folder, otherwise None
        """
        self.logger.debug("get_cubase_data: working on path %s" % filepath)
        pathsegments = filepath.split(os.path.sep)
        n = len(pathsegments)
        pluto_form = re.compile(r'^\w{2}-\d+')
    
        for s in reversed(pathsegments):
            if s == 'Audio':  # if there is an Audio folder, then the Cubase project should sit at that level
                self.logger.info("Found Audio at path level %d" % n)
                n -= 1
                cubasepath = os.path.sep.join(pathsegments[0:n])
                self.logger.debug("Suspect cubase path is at %s" % cubasepath)
                projects = glob("%s/*.cpr" % cubasepath)
                for p in projects:
                    self.logger.info("\tfound project %s" % p)
                    project_filename = os.path.basename(p)
                    if pluto_form.match(project_filename):
                        self.logger.info("\tHave PLUTO form! %s" % project_filename)
                        (filebase, ext) = os.path.splitext(project_filename)
                    
                        return {'is_cubase'      : True, 'cubase_filename': project_filename,
                                'cubase_filepath': os.path.dirname(cubasepath),
                                'project_id'     : filebase}
            n = -1
        self.logger.info("Could not find anything resembling a Cubase path")
        return None

    def potentialSidecarFilenames(self, filename, isxdcam=False):
        """
        Generator which yields all permutations of possible sidecar files for a given filename so that
        we can check if they exist
        :param filename: filename to investigate
        :param isxdcam: if True, then also yield for XDCAM-related names
        :return: yields results
        """
        for x in self.potentialSidecarExtensions:
            potentialFile = re.sub('\.[^\.]+', x, filename)
            yield potentialFile
        for x in self.potentialSidecarExtensions:
            potentialFile = filename + x
            yield potentialFile
        if isxdcam:
            for x in self.potentialSidecarExtensions:
                fileAppend = "M01{0}".format(x)
                potentialFile = re.sub('\.[^\.]+', fileAppend, filename)
                yield potentialFile
            
    def render_xml(self, fileref, preludeclip, preludeproject, xdcamref, cubaseref, externaldata, filepath, media_category="Rushes"):
        try:
            mdXML = self.mdTemplate.render({'fileref'       : fileref,
                                            'preluderef'    : preludeclip,
                                            'preludeproject': preludeproject,
                                            'xdcamref'      : xdcamref,
                                            'cubaseref'     : cubaseref,
                                            'externalmeta'  : externaldata,
                                            'category': media_category})
        except AttributeError as e:
            if 'to_vs_xml' in str(e):  # catch the case where we got no external metadata
                mdXML = self.mdTemplate.render({'fileref'       : fileref,
                                                'preluderef'    : preludeclip,
                                                'preludeproject': preludeproject,
                                                'xdcamref'      : xdcamref,
                                                'cubaseref'     : cubaseref,
                                                'externalmeta'  : "",
                                                'category': media_category})
            else:
                raise
    
        # run the compiled data through xmllint.  This should ensure that the XML is OK before we send, and also that
        # any pesky extender UTF-8 chars get escaped.
        proc = Popen(['xmllint', '--format', '-'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    
        # look at http://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout
        kill_proc = lambda p: p.kill()
        t = threading.Timer(self._timeout, kill_proc, [proc])
        t.start()
        try:
            (stdout, stderr) = proc.communicate(mdXML.encode("UTF-8"))
        finally:
            t.cancel()
    
        if proc.returncode != 0:
            self.logger.error("xmllint failed with code {1}: {0}".format(stderr, proc.returncode))
            fn = os.path.join(self.graveyard_folder, os.path.basename(filepath))
            self.logger.error("outputting failed XML to {0}".format(fn))
            with open(fn) as f:
                f.write(mdXML)
            raise XMLBuildError("xmllint on {0} failed: {1}".format(fn, stderr))
    
        return stdout
        
    def ask_pluto_for_projectid(self, filepath):
        from asset_folder_importer.pluto.assetfolder import AssetFolderLocator, ProjectNotFound
        l = AssetFolderLocator(scheme=self.cfg.value('pluto_scheme',default="http"), host=self.cfg.value('pluto_host'), port=self.cfg.value('pluto_port'),
                                user=self.cfg.value('vs_user'), passwd=self.cfg.value('vs_password'))
        
        test_path_segments = os.path.dirname(filepath).split('/')
        segsize = len(test_path_segments)
        n=0
        while True:
            try:
                if n==0:
                    test_path="/".join(test_path_segments)
                else:
                    test_path = "/".join(test_path_segments[0:n])
                self.logger.debug("{1} checking for asset folder at {0}".format(test_path, n))
                if n<-segsize:
                    return None #we've run out of path to check
                project_id = l.find_assetfolder(test_path)
                return project_id
            except ProjectNotFound:
                n-=1
            except IndexError:  #we've run out of path segments
                self.logger.debug("no more path segments to check")
                break
        return None
    
    def attempt_add_to_project(self, filepath, preludeproject, cubaseref, vsfile):
        VSprojectRef = VSCollection(host=self.cfg.value('vs_host'), port=self.cfg.value('vs_port'),
                                    user=self.cfg.value('vs_user'), passwd=self.cfg.value('vs_password'))
        if preludeproject:
            #if the item is attached to a prelude project that will immediately give us the project ID to attach to
            projectId = re.sub('\.[^\.]+$', '', preludeproject['filename'])
            # VSprojectRef.populate(projectId)
            VSprojectRef.name = projectId
        
            VSprojectRef.addToCollection(vsfile.memberOfItem, type="item")
            return True
        elif cubaseref:
            #if it's got a Cubase reference we can get the project ID from there
            try:
                VSprojectRef.populate(cubaseref['project_id'])
                VSprojectRef.addToCollection(vsfile.memberOfItem, type="item")
                return True
            except Exception as e:
                self.db.insert_sysparam("warning", "Unable to add %s to collection %s: %s" % (
                    vsfile.memberOfItem, cubaseref['project_id'], e))
                self.logger.warning("Warning: %s" % e)
                self.db.commit()
        else:
            #otherwise, ask Pluto's gnm_asset_folder plugin to look up the file path for us
            projectId = self.ask_pluto_for_projectid(filepath)
            if projectId is None:
                self.db.insert_sysparam("warning", "Pluto has no record of asset folder for %s" % filepath)
                self.logger.warning("Pluto has no record of asset folder for %s" % filepath)
                self.db.commit()
            else:
                VSprojectRef.name = projectId
                VSprojectRef.addToCollection(vsfile.memberOfItem, type="item")
                return True
        return False
    
    def run(self):
        from asset_folder_importer.pluto.assetfolder import HTTPError
        self.logger.info("In importer_thread::run...")
        while True:
            try:
                (fileref, filepath, rootpath) = self.queue.get(True,timeout=self._timeout)
                
                if fileref is None:
                    self.logger.info("Received null fileref, so teminating")
                    break
                
                result = self.attempt_file_import(fileref, filepath, rootpath)
                self.logger.debug(
                    "Data going into attempt_file_import: fileref = {0} filepath = {1} rootpath = {2}".format(fileref,
                                                                                                              filepath,
                                                                                                              rootpath))
                if isinstance(result, tuple) or isinstance(result, list):
                    (a, b, c) = result
                    self.found += a
                    self.withItems += b
                    self.imported += c
            except Empty:
                msgstring = "WARNING: importer_thread timed out waiting for more items"
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
            except VSFileInconsistencyError as e:
                msgstring = "Vidispine file inconsistency when trying to import {0}".format(filepath)
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
            except VSNotFound as e:
                msgstring = "WARNING: File %s was not found: %s" % (filepath, e)
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
                # exit(1)
            except HTTPError as e:
                msgstring = "WARNING: HTTP error communicating with Vidispine attempting to import %s: %s" % (
                filepath, e)
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
            except FileOnIgnoreList:
                self.ignored += 1
            except SweeperHTTPError as e:
                msgstring = "WARNING: HTTP error communicating with Vidispine attempting to import %s: %s" % (
                    filepath, e)
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
                self.portal_error = True
            except Exception as e:
                msgstring = "WARNING: error {0} occurred: {1}".format(e.__class__, e)
                self.logger.warning(msgstring)
                self.logger.warning(traceback.format_exc())
                self.db.insert_sysparam("warning", msgstring)
        self.logger.info("importer_thread completed")
    
    def check_file_set_permissions(self, fileref):
        """
        Calls the suid helper script to set permissions on the given file
        :param fileref: dictonary containing 'filepath' and 'filename' keys identifying the file to set
        :return: None
        """
        file = os.path.join(fileref['filepath'], fileref['filename'])
        if not os.path.exists(file):
            raise FileDoesNotExist(file)
        from subprocess import call
        try:
            call(["/bin/sudo", self._permissionscript, file])
        except Exception as e:
            self.logger.error("Error calling permissions script {0} on {1}: {2}".format(self._permissionscript, file, e))

    def import_tags_for_fileref(self,fileref):
        """
        Returns shape tags to transcode the incoming file to, dependent on the mime type of the incoming file
        :param fileref: dictionary containing the mime_type to check
        :return: list of shape tags, or None if none matching.
        """
        if fileref['mime_type'] and fileref['mime_type'].startswith("video/"):
            return['lowres']
        elif fileref['mime_type'] and fileref['mime_type'].startswith("audio/"):
            return ['lowaudio']
        elif fileref['mime_type'] and fileref['mime_type'].startswith("image/"):
            return ['lowimage']
        elif fileref['mime_type'] and fileref['mime_type'] == "application/mxf":
            return ['lowres']
        elif fileref['mime_type'] and fileref['mime_type'] == "model/vnd.mts":
            # mpeg transport streams are detected as this mimetype
            return ['lowres']
        return None
    
    def get_prelude_data(self, fileref, xdImporter):
        preludeclip = self.db.get_prelude_data(fileref['prelude_ref'])
    
        if preludeclip is None and xdImporter is not None:
            # if this is a supplementary XDCAM file then try to get prelude metadata for corresponding media
            for mediaFile in xdImporter.mediaFiles():
                mediaFile = os.path.abspath(mediaFile)
                mediaFileRef = self.db.fileRecord(mediaFile)
                if mediaFile is None:
                    break
            
                preludeclip = self.db.get_prelude_data(mediaFileRef['prelude_ref'])
                if preludeclip is not None:
                    break
        return preludeclip
                    
    def get_external_supplier_metadata(self, filepath):
        """
        Calls out to any defined external supplier ingest modules to try to find external supplier metadata for the given filename
        :param filepath: filepath to investigate
        :return: a Vidispine xml fragment of metadata if it exists, otherwise an empty string
        """
        try:
            provider_result = self.providers_list.try_file(os.path.dirname(filepath), os.path.basename(filepath))
            if provider_result is not None:
                return provider_result.to_vs_xml()
            else:
                return ""
        except LookupError as e:
            self.logger.error(str(e))
            return ""

    def do_real_import(self, vsfile, filepath,mdXML,import_tags):
        """
        Make the import call to vidispine, and wait for self._importer_timeout seconds for the job to complete.
        Raises a VSException representing the job error if the import job fails, or ImportStalled if the timeout occurs
        :param vsfile: VSFile object to import
        :param filepath: filepath of the VSFile
        :param mdXML: compiled metadata XML to import alongside the media
        :param import_tags: shape tags describing required transcodes
        :return: None
        """
        import_job = vsfile.importToItem(mdXML, tags=import_tags, priority="LOW", jobMetadata={"gnm_app": "vsingester"})

        job_start_time = time.time()
        close_sent = False
        while import_job.finished() is False:
            self.logger.info("\tJob status is %s" % import_job.status())
            if time.time() - job_start_time > self._importer_timeout:
                self.logger.error("\tJob has taken more than {0} seconds to complete, concluding that it must be stalled.".format(self._importer_timeout))
                import_job.abort()
                self.logger.error("\tSent abort signal to job")
                raise ImportStalled(filepath)
            if time.time() - job_start_time > self._close_file_timeout and not close_sent:
                vsfile.setState("CLOSED")
            sleep(5)
            import_job.update(noraise=False)

    def attempt_file_import(self, fileref, filepath, rootpath):
        """
        Performs the actual import of a file
        :param fileref: dictionary of information about the file
        :param filepath: path of the file
        :param rootpath: root path that we're importing from
        :return:
        """
        from asset_folder_importer.providers import LookupError
        withItems = 0
        imported = 0
        found = 0
        attempts = 0
        max_attempts = 3
        
        vsfile = None
        while True:
            try:
                vsfile = self.st.fileForPath(filepath)
                break
            except VSNotFound as e:
                if attempts > max_attempts:
                    self.logger.error("Unable to add file %s to Vidispine." % filepath)
                    raise
                self.logger.warning("File %s not found in Vidispine.  Attempting to update..." % filepath)
                try:
                    self.st.create_file_entity(filepath, createOnly=True)
                    time.sleep(1)  # sleep 1s to allow the file to be added
                except VSConflict:  # if the file was created in the meantime, don't worry about it, just retry the add
                    pass
                except HTTPError as e:
                    if e.code==503:
                        logging.warning("Received 503 when trying to create file entity.  Bailing out")
                        raise VSFileInconsistencyError(filepath)
                    else:
                        logging.warning("Received {0} HTTP error from Vidispine. Retrying.".format(e.code))

                attempts += 1
        
        if vsfile.memberOfItem is not None:
            self.logger.info("Found file %s in Vidispine at file id %s, item id %s" % (
                filepath, vsfile.name, vsfile.memberOfItem.name))
            self.db.update_file_vidispine_id(fileref['id'], vsfile.memberOfItem.name)
            self.attempt_add_to_project(os.path.join(fileref['filepath'],fileref['filename']), None, None, vsfile)
                
            withItems += 1
        else:
            self.logger.info(
                "Found file %s in Vidispine at file id %s, without an item membership" % (filepath, vsfile.name))
            if filepath.upper().endswith(".XMP"):
                self.logger.info("File is an XMP sidecar, will not attempt to import as an item")
                self.db.update_file_ignore(fileref['id'], True)
                raise FileOnIgnoreList(filepath)
            
            try:
                self.logger.info("Attempting to import...")
                path_parts = fileref['filepath'].split(os.sep)
                try:
                    fileref['likely_project'] = path_parts[7]
                except IndexError:
                    fileref['likely_project'] = "unknown project"

                try:
                    working_group = path_parts[5]
                    self.logger.info("Working group is {0}".format(working_group))
                    if working_group=="Branding":
                        media_category = "Branding"
                    else:
                        media_category = "Rushes"
                except IndexError:
                    media_category = "Rushes"

                xdImporter = None
                xdcamref = None
                fileref['xdcam_card'] = False
                if re.search('/BPAV/CLPR', fileref['filepath']):
                    self.logger.info("Got XDCAM file, probably")
                    
                    try:
                        xdImporter = XDCAMImporter(fileref['filepath'])
                        pprint(xdImporter.__dict__)
                        xdcamref = xdImporter.__dict__
                        fileref['xdcam_card'] = True
                    except Exception as e:
                        msgstring = "Unable to import XDCAM metadata from path defined by %s" % fileref['filepath']
                        self.db.insert_sysparam("warning", msgstring)
                        self.db.insert_sysparam("warning", str(e))
                        self.db.commit()
                else:
                    potentialXML = re.sub('\.[^\.]+', 'M01.XML',
                                          os.path.join(fileref['filepath'], fileref['filename']))
                    self.logger.info("Checking for potential XML at %s" % potentialXML)
                    if os.path.exists(potentialXML):
                        try:
                            xdImporter = XDCAMImporter(fileref['filepath'])
                        except InvalidDataError:  # this exception will get thrown as there is no SMI file
                            pass
                        self.logger.info("Trying to load xdcam sidecar %s" % potentialXML)
                        xdImporter.load(specificFile=potentialXML)
                        xdcamref = xdImporter.__dict__
                        pprint(xdcamref)
                        fileref['xdcam_card'] = True
                    else:
                        fileref['xdcam_card'] = False
                
                preludeproject = None
                
                preludeclip = self.get_prelude_data(fileref, xdImporter)

                if preludeclip is not None and preludeclip != {}:
                    preludeproject = self.db.get_prelude_project(preludeclip['parent_id'])
                
                cubaseref = self.get_cubase_data(fileref['filepath'], fileref['filename'])
                
                externaldata = self.get_external_supplier_metadata(filepath)
                
                mdXML = self.render_xml(fileref, preludeclip, preludeproject, xdcamref, cubaseref, externaldata,
                                        filepath, media_category=media_category)
                
                import_tags = self.import_tags_for_fileref(fileref)
                
                self.check_file_set_permissions(fileref)

                self.do_real_import(vsfile,filepath,mdXML,import_tags)
                
                imported += 1

                self.attempt_import_sidecar(rootpath, filepath, fileref, vsfile)

                # re-get the file information. Have some retries in case Vidispine hasn't caught up yet.
                for attempt in range(1, 10):
                    try:
                        vsfile = self.st.fileForPath(filepath)
                        if vsfile.memberOfItem is None:
                            raise NotFoundError("No item information found on imported file!")
                        
                        self.logger.warning("Updating file record with vidispine id %s" % vsfile.memberOfItem.name)
                        self.db.update_file_vidispine_id(fileref['id'], vsfile.memberOfItem.name)
                        break
                    except NotFoundError as e:
                        self.db.insert_sysparam("warning", e)
                        self.logger.warning("Warning: %s" % e)
                        self.db.commit()
                        # no point in doing the below, since it relies on having a project reference available
                        return (found, withItems, imported)
                    
                if not self.attempt_add_to_project(os.path.join(fileref['filepath'],fileref['filename']), preludeproject, cubaseref, vsfile):
                    return (found, withItems, imported)

            except FileDoesNotExist as e:
                self.logger.error("File {0} cannot be found on-disk, marking as deleted".format(str(e)))
                self.db.mark_id_as_deleted(fileref['id'])
            except VSJobFailed as e:
                msgstring = "WARNING: Vidispine import job failed: %s" % str(e)
                self.logger.error(msgstring)
                self.db.insert_sysparam("warning", msgstring)
            except VSBadRequest as e:
                msgstring = "WARNING: Vidispine import got a bad request: %s" % str(e)
                self.logger.error(msgstring)
                self.db.insert_sysparam("warning", msgstring)
                self.db.insert_sysparam("warning", "method: {0}, url: {1}, body: {2}".format(e.request_method, e.request_url,
                                                                                        e.request_body))
            except VSException as e:
                msgstring = "WARNING: Vidispine error when importing: %s" % str(e)
                self.logger.error(msgstring)
                self.db.insert_sysparam("warning", msgstring)
            except ImportStalled as e:
                msgstring = "WARNING: Import job timed out when trying to import: %s" % str(e)
                self.logger.error(msgstring)
                self.db.insert_sysparam("warning", msgstring)

        self.db.commit()
        found += 1
        
        return (found, withItems, imported)

    def attempt_import_sidecar(self, rootpath, filepath, fileref, vsfile):
        # Now see if there are any sidecar files that we should import against it
        for metafile in self.potentialSidecarFilenames(os.path.join(rootpath, filepath),
                                                       isxdcam=fileref['xdcam_card']):
            self.logger.info("Checking for potential sidecar at %s" % metafile)
            if os.path.exists(metafile):
                self.db.add_sidecar_ref(fileref['id'], metafile)
                self.logger.debug(
                    "Data going into add_sidecar_ref: fileref['id'] = {0} metafile = {1}".format(fileref['id'],
                                                                                                 metafile))
                self.logger.info("Attempting to import %s" % metafile)
                try:
                    if vsfile.memberOfItem is None:
                        self.logger.warning("Trying to import sidecar {0} for file {1}, file {1} is not a member of any item".format(metafile, vsfile.name))
                        return False
                    else:
                        vsfile.memberOfItem.importSidecar(metafile)
                        return True
                except VSNotFound as e:
                    self.logger.warning("Unable to find sidecar '%s': %s" % (metafile, e))
        return False
