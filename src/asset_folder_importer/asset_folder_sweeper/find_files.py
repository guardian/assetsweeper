import os
from pprint import pprint
import logging
import mimetypes
from asset_folder_importer.asset_folder_sweeper.posix_get_mime import posix_get_mime
from asset_folder_importer.asset_folder_sweeper.ignore_list import IgnoreList
logger = logging.getLogger(__name__)

global_ignore_list = IgnoreList()


def check_mime(fullpath,db):
    statinfo = os.stat(fullpath)
    mt = None
    try:
        (mt, encoding) = mimetypes.guess_type(fullpath, strict=False)
    except Exception as e:
        db.insert_sysparam("warning", e.message)

    if mt is None or mt == 'None':
        mt = posix_get_mime(fullpath, db)

    return statinfo, mt


def find_files(cfg,db, raven_client=None):
    """
    Find all relevant files and bung 'em in the database
    :param cfg: configuration object
    :param db: database object
    :param raven_client: raven client object for Sentry
    :return:
    """
    startpath = cfg.value('start_path',noraise=False)

    logger.info("Running from '%s'" % startpath)

    n=0
    for dirpath,dirnames,filenames in os.walk(startpath):
        for name in filenames:
            if name.startswith('.'):
                continue

            shouldIgnore = global_ignore_list.should_ignore(dirpath, name)

            fullpath = os.path.join(dirpath,name)
            raven_client.user_context({
                "dirpath": dirpath,
                "name": name,
                "shouldIgnore": shouldIgnore
            })

            logger.debug("Attempting to add file at path: '%s'" % fullpath)
            try:
                statinfo, mt = check_mime(fullpath,db)
                raven_client.user_context({
                    "statinfo": statinfo,
                    "mt": mt
                })

                db.upsert_file_record(dirpath,name,statinfo,mt,ignore=shouldIgnore)

            except UnicodeDecodeError as e:
                db.insert_sysparam("warning",str(e))
                raven_client.captureException()
                logging.error(str(e))
            except UnicodeEncodeError as e:
                db.insert_sysparam("warning",str(e))
                raven_client.captureException()
                logging.error(str(e))
            except OSError as e:
                if e.errno == 2: #No Such File Or Directory
                    db.insert_sysparam("warning", "File {0} was missing".format(dirpath))
                    db.mark_id_as_deleted(dirpath,name)
                else:
                    db.insert_sysparam("warning", "Could not stat {0}: {1}".format(dirpath, str(e)))
                    raven_client.captureException()
            n+=1
            print "%d files...\r" %n

    return n