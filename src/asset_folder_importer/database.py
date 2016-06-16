__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = '$Rev$ $LastChangedDate$'

import psycopg2
from elasticsearch.client import Elasticsearch
from elasticsearch.exceptions import *
import elasticsearch.helpers
import traceback
import re
from pprint import pprint
import platform
import os
import datetime as dt
import logging
from datetime import datetime, timedelta

DEFAULT_INDEX = "assetimporter"


class DataError(StandardError):
    pass


class ArgumentError(StandardError):
    pass


class AlreadyLinkedError(StandardError):
    pass


class ElasticSearchCommitter(object):
    DT_SYSTEM = "system"
    DT_FILE = "file_entry"
    DT_PROJECT = "prelude_project"
    DT_PRELUDE = "prelude_entry"
    DT_SIDECAR = "sidecar"

    class IncompleteCommitError(StandardError):
        pass

    def __init__(self, hostlist="localhost", indexname=None, commit_interval=100):
        if indexname is None:
            raise ValueError("You must supply an index name")

        if not isinstance(hostlist,list):
            hostlist = [hostlist]
        self._elastic = Elasticsearch(hostlist)
        self._actions = []
        self._indexname = indexname
        self.commit_interval = commit_interval
        self._logger = logging.getLogger("ElasticSearchCommitter")
        self.set_library_loglevel()

    def __del__(self):
        self.commit()

    @staticmethod
    def set_library_loglevel(level=logging.ERROR):
        """
        Sets the log level of the elasticsearch and urllib libraries to the requested level, or ERROR if none set
        :param level: level to set to (logging.DEBUG, logging.ERROR, etc.). Defaults to logging.ERROR if nothing set
        :return: None
        """
        eslogger = logging.getLogger('elasticsearch')
        eslogger.level = level
        eslogger = logging.getLogger('urllib3.connectionpool')
        eslogger.level = level
        eslogger = logging.getLogger('urllib3.util.retry')
        eslogger.level = level

    def setup_index(self):
        if self._elastic.indices.exists(index=DEFAULT_INDEX):
            return
        self._elastic.indices.create(index=DEFAULT_INDEX,
                                     body={
                                         'settings': {
                                             'number_of_replicas': 0,
                                             "analysis": {
                                                  "analyzer": {
                                                    "path-analyzer": {
                                                      "type": "custom",
                                                      "tokenizer": "path-tokenizer"
                                                    }
                                                  },
                                                  "tokenizer": {
                                                    "path-tokenizer": {
                                                      "type": "path_hierarchy",
                                                      "delimiter": "."
                                                    }
                                                  }
                                             }
                                         },
                                         'mappings': {
                                             self.DT_FILE: {
                                                 "properties": {
                                                     "filename": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "filepath": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "filepath_analyzed": {
                                                         "type": "string",
                                                         "analyzer": "path-analyzer"
                                                     },
                                                     "mime": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "ignore": {
                                                         "type": "boolean"
                                                     },
                                                     "imported_id": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "initial_project_id": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     }
                                                 }
                                             },
                                             self.DT_PRELUDE: {
                                                 "properties": {
                                                     "asset_name": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "asset_type": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "class_id": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "drop_frame": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "project": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                 }
                                             },
                                             self.DT_SIDECAR: {
                                                 "properties": {
                                                     "file_ref": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "sidecar_path": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "sidecar_path_analyzed": {
                                                         "type": "string",
                                                         "analyzer": "path-analyzer"
                                                     },
                                                     "sidecar_name": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                 }
                                             },
                                             self.DT_PROJECT: {
                                                 "properties": {
                                                     "filepath": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "filepath_analyzed": {
                                                         "type": "string",
                                                         "analyzer": "path-analyzer"
                                                     },
                                                     "filename": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "uuid": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                     "version": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     },
                                                 }
                                             },
                                             self.DT_SYSTEM: {
                                                 "properties": {
                                                     "timestamp": {
                                                         "type": "date",
                                                     },
                                                     "script_version": {
                                                         "type": "string",
                                                         "index": "not_analyzed"
                                                     }
                                                 }
                                             }
                                         }
                                     })

    def add(self,doc_type,doc_data,doc_id=None):
        self.enqueue("index",doc_type,doc_data,doc_id)

    def update(self,doc_type,doc_data,doc_id=None):
        self.enqueue("update",doc_type,{'_retry_on_conflict': 100, 'doc': doc_data},doc_id)

    def delete(self,doc_type,doc_id):
        self.enqueue("delete",doc_type,None,doc_id)

    def enqueue(self,op,doc_type,doc_data,doc_id):
        if not isinstance(doc_type,basestring):
            raise TypeError("doc_type must be a string")
        if not isinstance(doc_data,dict):
            raise TypeError("doc_data must be a dict")

        r={
            '_op_type': op,
            '_index': self._indexname,
            '_type': doc_type,
        }
        if doc_data is not None:
            r.update(doc_data)
            #r['_source'] = doc_data

        if doc_id is not None:
            r['_id'] = doc_id

        self._actions.append(r)

        if len(self._actions)>self.commit_interval:
            self.commit()

    def commit(self):
        try:
            (success_numbers,error_list) = elasticsearch.helpers.bulk(self._elastic,self._actions)
        except RequestError:
            pprint(self._actions)
            raise
        except TransportError:
            pprint(self._actions)
            raise
        except elasticsearch.helpers.BulkIndexError:
            pprint(self._actions)
            raise
        self._logger.info("Committed %d items to index" % success_numbers)
        self._actions = []
        n=0
        if success_numbers < n:
            raise self.IncompleteCommitError("\t\n".join(error_list))
        return success_numbers


class importer_db:
    def __init__(self,clientversion,hostname="localhost",port="5432",username="",password="",elastichosts=""):
        portnum=5432
        try:
            portnum=int(port)
        except Exception:
            pass

        #self.conn = psycopg2.connect(database="asset_folder_importer",user=username,password=password,host=hostname,port=portnum)
        self.clientversion=clientversion
        self._logger = logging.getLogger('importer_db')

        if elastichosts is not None:
            if not isinstance(elastichosts,list):
                elastichosts = [elastichosts]
            self._escommitter = ElasticSearchCommitter(elastichosts,DEFAULT_INDEX)
            self._escommitter.setup_index()
        else:
            raise ValueError("This version of importer_db requires at least one Elastic Search host to connect to")
            #self._escommitter = None

    def __del__(self):
        # self.conn.commit()
        self._escommitter.commit()

    def update_schema_20(self):
        pass
        # cursor = self.conn.cursor()
        # sqlcmd = """
        # CREATE TABLE deleted_files (
        #     id integer NOT NULL,
        #     filepath text NOT NULL,
        #     filename text NOT NULL,
        #     mtime timestamp with time zone,
        #     ctime timestamp with time zone,
        #     atime timestamp with time zone,
        #     imported_id character varying(16),
        #     imported_at timestamp without time zone,
        #     last_seen timestamp with time zone,
        #     size bigint,
        #     owner integer,
        #     gid integer,
        #     prelude_ref integer,
        #     ignore boolean DEFAULT false,
        #     mime_type character varying(256)
        # );
        # """
        # cursor.execute(sqlcmd)

    def update_schema_21(self):
        pass
        # cursor = self.conn.cursor()
        # sqlcmd = """
        # ALTER TABLE edit_projects ADD COLUMN valid boolean,
        #     ADD COLUMN problem text,
        #     ADD COLUMN problem_detail text;
        # """
        # cursor.execute(sqlcmd)
        # self.conn.commit()

    def _has_table(self,tablename,schemaname="public"):
        pass
        # cursor = self.conn.cursor()
        # sqlcmd = """
        # SELECT EXISTS (
        #     SELECT 1
        #     FROM   pg_catalog.pg_class c
        #     JOIN   pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        #     WHERE  n.nspname = %s
        #     AND    c.relname = %s
        #     AND    c.relkind = 'r'
        # );
        # """
        # logging.debug("Checking for existence of table {0} in schema {1}".format(tablename,schemaname))
        # #logging.debug(sqlcmd)
        # cursor.execute(sqlcmd, (schemaname,tablename))
        # row = cursor.fetchone()
        # return row[0]

    def _has_column(self,tablename,columnname):
        pass
        # #select column_name from information_schema.columns where table_name='edit_projects' and column_name='clips'
        # cursor = self.conn.cursor()
        # sqlcmd="select column_name from information_schema.columns where table_name=%s and column_name=%s"
        # logging.debug("Checking for existence of column {0} in table {1}".format(tablename,columnname))
        # cursor.execute(sqlcmd, (tablename,columnname))
        # if cursor.fetchone() is not None:
        #     return True
        # return False

    def check_schema_20(self):
        pass
        # if not self._has_table('deleted_files'):
        #     self.update_schema_20()

    def check_schema_21(self):
        pass
        # if not self._has_column('edit_projects','valid'):
        #     self.update_schema_21()

    def make_sysparam_docid(self):
        return "run_{0}_sysparams".format(os.getpid())

    def insert_sysparam(self,key,value):
        #cursor=self.conn.cursor()
        #for attempt in range(1,10):
            # try:
            #     cursor.execute("insert into system (key,value,pid) values (%s,%s,%s)", (key, value, os.getpid()))
            #     break
            # except psycopg2.InternalError: #if we have an aborted transaction, cleanup and then re-try
            #     self.conn.rollback()
            #     continue
            #try:
        doc = {}
        doc[key]=value
        doc['timestamp'] = datetime.now()
        doc_id = self.make_sysparam_docid()

        self._escommitter.update(ElasticSearchCommitter.DT_SYSTEM,doc,doc_id)

    def purge_system_messages(self,since):
        if not isinstance(since,timedelta):
            raise TypeError("You need to provide a timedelta to this function")

        #timestr = 'P{years}-{months}-{days}'.format(years=0,months=0,days=int(since.days))
        # sqlcmd = "delete from system where now()-timestamp > '{0}'".format(timestr)
        # #print "sql command is %s" % sqlcmd
        # cursor = self.conn.cursor()
        # cursor.execute(sqlcmd)
        time_limit = datetime.now() - since

        #empty out the commit buffer
        self._escommitter.commit()

        for item in elasticsearch.helpers.scan(self._escommitter._elastic,
                                   index=self._escommitter._indexname,
                                   query={
                                       'query': {
                                           'filtered': {
                                               'filter': {
                                                   'range': {
                                                       'timestamp': {
                                                           #this format seems to work...
                                                           'lt': time_limit.strftime("%Y-%m-%dT%H:%M:%S")
                                                       }
                                                   }
                                               }
                                           }
                                       }
                                   }):
            self._escommitter.delete(ElasticSearchCommitter.DT_SYSTEM,item['_id'])

        #make sure that they're done
        self._escommitter.commit()


    def commit(self):
        #self.conn.commit()
        try:
            self._escommitter.commit()
        except RequestError:
            pass

    def cleanuperror(self):
        pass
        # try:
        #     self.conn.commit()
        # except Exception:
        #     pass
        #
        # self.conn.rollback()

# select * from system where ((key='exit' and value like '%') or (key='script_version' or key='run_start'))
#  and pid in (select pid from system where key='script_version' and value like 'premiere_get_referenced_media%')
#  order by timestamp desc

    def pid_for_status(self,statusid,limit=1):
        if not statusid:
            raise ArgumentError("pid_for_status needs a status id")

        # cur = self.conn.cursor()
        # cur.execute("select pid from system where key='exit' and value='%s' order by timestamp desc limit %s", (statusid,limit))
        # for result in cur.fetchall():
        #     yield result[0]
        data = self._escommitter._elastic.search(index=DEFAULT_INDEX,
                                                 body={'query': {
                                                     'filtered': {
                                                         'filter': {
                                                             'match': {
                                                                 'exit': statusid
                                                             }
                                                         }
                                                     }
                                                 }})
        self._logger.debug('Got {0} results'.format(data['hits']['total']))
        for doc in data['hits']['hits']:
            if 'pid' in doc:
                yield doc['_source']['pid']
            else:
                self._logger.error('system doc {0} does not have a pid associated with it'.format(doc['_id']))

    def lastrun_endtime(self, status=None):
        try:
            return self.lastrun_gettime('run_end', status=status)
        except DataError as e:
            self._logger.warning(e)
            return None

    def lastrun_starttime(self, status=None):
        try:
            return self.lastrun_gettime('run_start', status=status)
        except DataError as e:
            self._logger.warning(e)
            return None

    def lastrun_gettime(self, field, status=None):
        if not self.clientversion:
            raise ArgumentError("Cannot call database::lastrun_endtime without the client name/version string set. Call __init__ properly first.")

        matches = re.search(u'^([\w\d_\-]+)',self.clientversion)
        if matches is None:
            raise ArgumentError("database::lastrun_endtime - Client version string does not provide a script name to search for at the start")

        scriptname = matches.group(1)
        #logging.debug("database::lastrun_endtime - script name determined as %s",scriptname)

        filterlist = [
            {
                "prefix": {
                    "script_version": scriptname
                }
            }
        ]

        # if status is None:
        #     querystring = "select value from system where key='{0}' and pid=(select pid from system where key='script_version' and value like '{1}%' order by timestamp desc limit 1)".format(field, scriptname)
        # else:
        #     querystring = """select value from system where key='{0}'
        #                     and pid in (select pid from system where key='script version' and value like '{1}%'
        #                         and pid in (select pid from system where key='exit' and value='{2}')) limit 1
        #                 """.format(field,scriptname,status)
        if status is not None:
            filterlist.append({
                "match": {
                    "exit": status
                }
            })

        try:
            data = self._escommitter._elastic.search(index=DEFAULT_INDEX,
                                          body={
                                              'query': {
                                                  'filtered': {
                                                      'filter': {
                                                          'and': filterlist
                                                      }
                                                  }
                                              },
                                              'sort': {
                                                  'timestamp': {
                                                      'order': 'desc'
                                                  }
                                              }
                                          },
                                          size=1)
        except TransportError as e:
            pprint({
                  'query': {
                      'filtered': {
                          'filter': {
                              'and': filterlist
                          }
                      }
                  },
                  'sort': {
                      'timestamp': {
                          'order': 'desc'
                      }
                  }
              })
            raise

        if data['hits']['total'] == 0:
            return None

        doc = data['hits']['hits'][0]
        if not field in doc:
            raise DataError("returned system status doc had no {0} field".format(field))
        return doc[field]

        # cursor = self.conn.cursor()
        # cursor.execute(querystring)
        # result = cursor.fetchone()
        #
        # if result is None:
        #     return None #this means that the script is either still running or crashed last time around
        #
        # timestamp = dt.datetime.strptime(result[0],"%Y-%m-%dT%H:%M:%S.%f")
        #
        # return timestamp

    def mark_id_as_deleted(self, id):
        #if not isinstance(id,int): raise ValueError()

        sqlcmd = """
        insert into deleted_files
        (id,filepath,filename,mtime,ctime,atime,imported_id,imported_at,last_seen,size,owner,gid,prelude_ref,ignore,mime_type)
            select id,filepath,filename,mtime,ctime,atime,imported_id,imported_at,last_seen,size,owner,gid,prelude_ref,ignore,mime_type
            from files
            where id=%s
        """
        #self._escommitter.delete(doc_type=ElasticSearchCommitter.DT_FILE,doc_id=id)
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_id=id,
                                 doc_data={
                                     'deleted': True,
                                     'deleted_at': datetime.now(),
                                 })

    def start_run(self):
        self._escommitter.add(doc_type=ElasticSearchCommitter.DT_SYSTEM,
                              doc_data={},
                              doc_id=self.make_sysparam_docid())
        self.insert_sysparam('running_host',platform.node())
        self.insert_sysparam('script_version',self.clientversion)
        self.insert_sysparam('python_version',platform.python_version())
        self.insert_sysparam('OS',platform.system())
        self.insert_sysparam('OS_release',platform.release())
        self.insert_sysparam('OS_version',platform.version())
        self.insert_sysparam('run_start',dt.datetime.now())
        #self.conn.commit()
        self.commit()

    def end_run(self,status=None):
        self.insert_sysparam('run_end',dt.datetime.now())
        if status is not None:
            self.insert_sysparam('exit',status)
        #self.conn.commit()

    def project_type_for_extension(self,xtn,desc=None,opens_with=None):
        pass
        # cursor = self.conn.cursor()
        #
        # cursor.execute("select id from edit_project_types where extension='%s'" % xtn)
        # result=cursor.fetchone()
        #
        # if result is None:
        #     cursor.execute("insert into edit_project_types (extension,description,opens_with) values (%s,%s,%s) returning id", (xtn,desc,opens_with))
        #     result=cursor.fetchone()
        #
        # id=result[0]
        #
        # return id

    @staticmethod
    def make_doc_id(doc):
        doc_id = re.sub('^[\w\d]','',doc['filepath']+doc['filename'])
        return doc_id

    def upsert_edit_project(self,filepath,filename,uuid,version,desc=None,opens_with=None):
        #cursor = self.conn.cursor()

        matches=re.search(u'(\.[^\.]+)$',filename)
        file_xtn=""
        if matches is not None:
            file_xtn=str(matches.group(1))
        else:
            raise ArgumentError("Filename %s does not appear to have a file extension" % filename)

        #typenum=self.project_type_for_extension(file_xtn,desc=desc,opens_with=opens_with)

        doc = {
            'filename': filename,
            'filepath': filepath,
            'lastseen': datetime.now(),
            'valid': True,
            'desc': desc,
            'opens_with': opens_with
        }
        doc_id = self.make_doc_id(doc)
        self._escommitter.add(ElasticSearchCommitter.DT_PROJECT,doc,doc_id)

        # try:
        #     cursor.execute("insert into edit_projects (filename,filepath,type,lastseen,valid) values (%s,%s,%s,now(),true) returning id", (filename,filepath,typenum))
        # except psycopg2.IntegrityError as e:
        #     self.conn.rollback()
        #     cursor.execute("update edit_projects set lastseen=now(), valid=true where filename=%s and filepath=%s returning id", (filename,filepath))
        #
        # result = cursor.fetchone()
        # id = result[0]
        #
        # sqlcmd="update edit_projects set uuid=%s, version=%s where id=%s"
        # cursor.execute(sqlcmd, (uuid,version,id))
        # self.conn.commit()
        return doc_id

    def log_project_issue(self,filepath,filename,problem="",detail="",desc=None,opens_with=None):
        cursor = self.conn.cursor()

        matches=re.search(u'(\.[^\.]+)$',filename)
        file_xtn = ""
        if matches is not None:
            file_xtn=str(matches.group(1))
        else:
            raise ArgumentError("Filename %s does not appear to have a file extension" % filename)

        #typenum=self.project_type_for_extension(file_xtn,desc=desc,opens_with=opens_with)

        doc = {
            'filename': filename,
            'filepath': filepath,
            'problem': problem,
            'problem_detail': detail,
            'lastseen': datetime.now(),
            'valid': False
        }
        doc_id = self.make_doc_id(doc)
        self._escommitter.update(ElasticSearchCommitter.DT_PROJECT,doc,doc_id)

        # try:
        #     cursor.execute("""insert into edit_projects (filename,filepath,type,problem,problem_detail,lastseen,valid)
        #     values (%s,%s,%s,%s,%s,now(),false) returning id""", (filename,filepath,typenum,problem,detail))
        # except psycopg2.IntegrityError as e:
        #     print str(e)
        #     print traceback.format_exc()
        #     self.conn.rollback()
        #     cursor.execute("""update edit_projects set lastseen=now(), valid=false, problem=%s, problem_detail=%s where filename=%s and filepath=%s returning id""", (problem,detail,filename,filepath))
        # #print cursor.mogrify("""update edit_projects set lastseen=now(), valid=false, problem=%s, problem_detail=%s where filename=%s and filepath=%s returning id""", (problem,detail,filename,filepath))
        # result=cursor.fetchone()
        # id = result[0]
        # self.conn.commit()
        return doc_id

    def link_file_to_edit_project(self,fileid,projectid):
        # cursor=self.conn.cursor()
        #
        # cursor.execute("select count(id) from edit_project_clips where file_ref=%s and project_ref=%s", (fileid,projectid))
        # result=cursor.fetchone()
        #
        # if result[0]>0:
        #     raise AlreadyLinkedError("File id %s is already linked to project %s" % (fileid,projectid))
        #
        # cursor.execute("insert into edit_project_clips (file_ref,project_ref) values (%s,%s)", (fileid,projectid))
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_data={'parent_project': projectid},doc_id=fileid)

    def update_file_record_gone(self,filepath,filename):
        # cursor = self.conn.cursor()
        # self.conn.commit()
        #
        # try:
        #     cursor.execute("update files set ignore=true where filename=%s and filepath=%s", (filename, filepath))
        # except Exception as e:
        #     logging.warning("Unable to update to ignore gone file: %s" % str(e))
        #     self.insert_sysparam("warning",str(e))

        doc = self.fileRecord(os.path.join(filepath,filename))
        doc_id = doc['id']
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_data={'ignore': True},doc_id=doc_id)

    def upsert_file_record(self,filepath,filename,statinfo,mimetype,ignore=None):
        # cursor=self.conn.cursor()
        #
        # self.conn.commit()
        #print "trace: upsert_file_record: %s/%s" %(filepath,filename)

        #sqlcmd="select * from upsert_file('%s','%s')" % (filepath,filename)
        #print "about to exec %s" %sqlcmd

        #cursor.execute(sqlcmd)
        doc = {
            'filename': filename,
            'filepath': filepath,
            'filepath_analyzed': filepath,
            'mtime': datetime.utcfromtimestamp(statinfo.st_mtime),
            'atime': datetime.utcfromtimestamp(statinfo.st_atime),
            'ctime': datetime.utcfromtimestamp(statinfo.st_ctime),
            'size': statinfo.st_size,
            'oid': statinfo.st_uid,
            'gid': statinfo.st_gid,
            'mime': mimetype,
            'ignore': False,
            'lastseen': datetime.now()
        }
        if ignore is not None:
            doc['ignore'] = ignore

        self._escommitter.add(doc_type=ElasticSearchCommitter.DT_FILE,doc_id=self.make_doc_id(doc),doc_data=doc)


    def fileRecord(self,path):
        #cursor=self.conn.cursor()

        # #FIXME: this should be separated out into a seperate path mapping object, maybe inside config
        path = re.sub(u'^/Volumes','/srv',path)
        #
        # #print "looking for file %s in %s" % (os.path.basename(path),os.path.dirname(path))
        #
        # cursor.execute("select * from files where filepath=%s and filename=%s",(os.path.dirname(path),os.path.basename(path)))
        # fields = map(lambda x: x[0], cursor.description)
        # result=cursor.fetchone()
        #
        # if result:
        #     #print "got id %s" % result[0]
        #     return dict(zip(fields,result))
        # return None

        q={
                                               'query': {
                                                   'filtered': {
                                                       'filter': {
                                                           'and':[
                                                               {
                                                               'term': {
                                                                   'filepath': os.path.dirname(path)
                                                               }},
                                                               {'term': {
                                                                   'filename': os.path.basename(path)
                                                               }
                                                               }
                                                           ]
                                                       }
                                                   }
                                               }
                                           }
        #pprint(q)
        result = self._escommitter._elastic.search(index=DEFAULT_INDEX,
                                           body=q)
        if result['hits']['total'] == 0:
            return None
        r = result['hits']['hits'][0]['_source']
        r['id'] = result['hits']['hits'][0]['_id']
        return self._fix_dates(r)

    def fileId(self,path):
        path = re.sub(u'^/Volumes','/srv',path)

        rec = self.fileRecord(path)
        if rec is not None:
            return rec['id']
        return None

    def filesForVSID(self,vsid=None,showIgnore=False):
        filter_list = [
#            {
#                'or': [
#                    {"missing": {'field': "deleted"}},
#                    {
#                        'deleted': False
#                    }
#                ]
#            }
        ]

        if vsid is None:
            filter_list.append({'missing': {'field': 'imported_id'}})
        else:
            filter_list.append({
                'term': {
                    'imported_id': vsid
                }
            })

        if showIgnore == False:
            filters = {
                #show anything with either ignore field not set (not yet checked) or false
                'or': [
                    {
                        'missing': {
                            "field": 'ignore'
                        }
                    },
                    {
                        'term': {
                            "ignore": False
                        }
                    }
                ]
            }
            #filter_list.append(filters)

        for item in elasticsearch.helpers.scan(self._escommitter._elastic,
                                               index=DEFAULT_INDEX,
                                               query={
                                                    'query': {
                                                        'filtered': {
                                                            'filter': {
                                                                'and': filter_list
                                                            }
                                                        }
                                                    }
                                               }):
            doc = item['_source']
            doc['id'] = item['_id']
            yield self._fix_dates(doc)
        # for result in cursor:
        #     yield dict(zip(fields,result))

    def files_not_connected_to_project(self):
        filter_list = [
            {
                'match': {
                    '_type': ElasticSearchCommitter.DT_FILE
                }
            },
            {
                'not': {
                    'exists': {
                        'field': 'initial_project_id'
                    }
                }

            }
        ]
        for item in elasticsearch.helpers.scan(self._escommitter._elastic,
                                                index=DEFAULT_INDEX,
                                                query={
                                                    'query': {
                                                        'filtered': {
                                                            'filter': {
                                                                'and': filter_list
                                                            }
                                                        }
                                                    },
                                                    'sort': [
                                                        {
                                                            'ctime': {
                                                                'order': 'desc'
                                                            }
                                                        }
                                                    ]
                                                }):
            doc = item['_source']
            doc['id'] = item['_id']
            yield self._fix_dates(doc)

    #since should be a datetime object
    def files(self,since=None,pathspec=None,namespec=None,reverse_order=False):
        filter_list = [
            {
                'match': {
                    '_type': ElasticSearchCommitter.DT_FILE
                }
            },
            {
                'match': {
                    'deleted': False
                }
            }
        ]

        if since is not None:
            filter_list.append({
                'range': {
                    'lastseen': {
                        'gte': since
                    }
                }
            })

        if pathspec is not None:
            filter_list.append({
                'prefix': {
                    'filepath': pathspec
                }
            })

        if namespec is not None:
            filter_list.append({
                'wildcard': {
                    'filename': "*"+namespec+"*"
                }
            })

        if reverse_order:
            sort_dir = 'desc'
        else:
            sort_dir = 'asc'

        for item in elasticsearch.helpers.scan(self._escommitter._elastic,
                                                index=DEFAULT_INDEX,
                                                query={
                                                    'query': {
                                                        'filtered': {
                                                            'filter': {
                                                                'and': filter_list
                                                            }
                                                        }
                                                    },
                                                    'sort': [
                                                        {
                                                            'ctime': {
                                                                'order': sort_dir
                                                            }
                                                        }
                                                    ]
                                                }):
            doc = item['_source']
            doc['id'] = item['_id']
            yield self._fix_dates(doc)

    def _fix_dates(self,doc):
        """
        fixes the strings returned as dates into datetimes
        :param doc:
        :return:
        """
        import dateutil.parser
        rtn = doc
        for k,v in doc.items():
            try:
                d = dateutil.parser.parse(v)
                if d is not None:
                    rtn[k] = d
                #print "converted {1} into {2}"
            except StandardError as e:
                pass #print "{0} ({1}): {2}".format(v,k,e) 
        return rtn

    def update_file_ignore(self,fileid,ignflag):
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_data={'ignore': ignflag},doc_id=fileid)

    def update_file_vidispine_id(self,fileid,vsid):
        # cursor=self.conn.cursor()
        #
        # if not isinstance(fileid,int):
        #     raise ArgumentError("fileid argument must be an integer")

        if not re.match(u'^\w{2}-\d+',vsid):
            msg="Vidispine id {0} does not look like an integer".format(vsid)
            raise ArgumentError(msg)

        # cursor.execute("update files set imported_id='{0}',imported_at=now() where id={1}".format(vsid,fileid))
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_data={'imported_id': vsid},doc_id=fileid)

    def upsert_prelude_project(self,path=None,filename=None,uuid=None,version=None,nclips=None):
        doc = {
            'filepath': path,
            'filename': filename,
            'uuid': uuid,
            'version': version,
            'clips': nclips,
            'lastseen': datetime.now()
        }
        doc_id = self.make_doc_id(doc)

        self._escommitter.add(doc_type=ElasticSearchCommitter.DT_PROJECT,doc_data=doc,doc_id=doc_id)
        return doc_id

    def update_project_nclips(self,nclips, projectid=None):
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_PROJECT,
                                 doc_data={
                                     'clips': nclips
                                 },
                                 doc_id=projectid)

    def upsert_prelude_clip(self,project_ref=None,asset_name=None,asset_relink_skipped=None,asset_type=None,
            uuid=None,created_date=None,drop_frame=None,duration=None,file_path=None,frame_rate=None,
            import_date=None,parent_uuid=None,start_time=None):

        doc = locals() #should get a dict of the arguments
        del doc['self']

        if uuid is not None:
            doc_id = uuid
        else:
            doc_id=project_ref + asset_name

        self._escommitter.add(doc_type=ElasticSearchCommitter.DT_PRELUDE,
                              doc_data=doc,
                              doc_id=doc_id)
        return doc_id

    def get_prelude_data(self,preludeid):
        if preludeid is None:
            return None
        data = self._escommitter._elastic.get(index=DEFAULT_INDEX,doc_type=ElasticSearchCommitter.DT_PRELUDE,id=preludeid)
        return data['_source']

    def get_prelude_project(self,projid):
        data = self._escommitter._elastic.get(index=DEFAULT_INDEX,doc_type=ElasticSearchCommitter.DT_PROJECT,id=projid)
        return data['_source']

    def update_prelude_clip_fileref(self,preludeid,fileid):
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_FILE,doc_data={'prelude_ref': preludeid},doc_id=fileid)
        self._escommitter.update(doc_type=ElasticSearchCommitter.DT_PRELUDE,doc_data={'file_reference': fileid},doc_id=preludeid)

    def add_sidecar_ref(self,fileid,sidecar_path):
        (sidecar_dir,sidecar_name)=os.path.split(sidecar_path)

        self._escommitter.add(doc_type=ElasticSearchCommitter.DT_SIDECAR,
                              doc_data={
                                  'file_ref': fileid,
                                  'sidecar_dir': sidecar_dir,
                                  'sidecar_name': sidecar_name
                              })


if __name__ == '__main__':
    from pprint import pprint
    d = importer_db('testing',elastichosts='dc1-mmlb-01.dc1.gnm.int:9200')
    data=d.fileRecord('/srv/Proxies2/DevSystem/Assets/Multimedia_Culture_and_Sport/Andrew_Collins_Telly_Addict/mona_mahmood_March_2_2015Andrew_Collins_Telly_Addict/9 March Episode/Untitled/BPAV/CLPR/559_1409_01/559_1409_01.MP4')
    pprint(data)
