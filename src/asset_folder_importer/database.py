__author__ = 'Andy Gallagher <andy.gallagher@theguardian.com>'
__version__ = '$Rev$ $LastChangedDate$'

import psycopg2
import traceback
import re
import platform
import os
import datetime as dt
import logging


class DataError(StandardError):
    pass


class ArgumentError(StandardError):
    pass


class AlreadyLinkedError(StandardError):
    pass


class importer_db:
    def __init__(self,clientversion,hostname="localhost",port="5432",username="",password="", dbname="asset_folder_importer"):
        portnum=5432
        try:
            portnum=int(port)
        except Exception:
            pass

        self.conn = psycopg2.connect(database=dbname,user=username,password=password,host=hostname,port=portnum)
        self.clientversion=clientversion

        sqlcmd = """create or replace function upsert_file(fp text, fn text) returns INTEGER as
        $$
        begin
            loop
                update files set last_seen=now() where filename=fn and filepath=fp returning id;
                if id then
                    return id;
                end if;
                begin
                    insert into files (filename,filepath,last_seen) values (fn,fp,now()) returning id;
                    return id;
                exception when unique_violation then
                    -- do nothing, just re-try the update
                end;
            end loop;
        end;
        $$
        language plpgsql;
        """
        cursor=self.conn.cursor()
        try:
            #cursor.execute("drop function if exists upsert_file (text,text)")
            cursor.execute(sqlcmd)
            self.conn.commit()
        except psycopg2.ProgrammingError as e:
            print "Warning: %s" % e.message
            self.conn.rollback()

    def __del__(self):
        self.conn.commit()

    def update_schema_20(self):
        cursor = self.conn.cursor()
        sqlcmd = """
        CREATE TABLE deleted_files (
            id bigint NOT NULL,
            filepath text NOT NULL,
            filename text NOT NULL,
            mtime timestamp with time zone,
            ctime timestamp with time zone,
            atime timestamp with time zone,
            imported_id character varying(16),
            imported_at timestamp without time zone,
            last_seen timestamp with time zone,
            size bigint,
            owner integer,
            gid integer,
            prelude_ref integer,
            ignore boolean DEFAULT false,
            mime_type character varying(256)
        );
        """
        cursor.execute(sqlcmd)

    def update_schema_21(self):
        cursor = self.conn.cursor()
        sqlcmd = """
        CREATE TABLE edit_projects (
    id integer NOT NULL,
    type integer NOT NULL,
    filepath text NOT NULL,
    filename text NOT NULL,
    uuid uuid,
    version text,
    clips integer,
    lastseen timestamp with time zone,
    valid boolean,
    problem text,
    problem_detail text
);
        ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_projects_pkey PRIMARY KEY (id);
    ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_projects_unique_filepath UNIQUE (filepath, filename);
    ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_project_type_fkey FOREIGN KEY (type) REFERENCES edit_project_types(id);
    """
        cursor.execute(sqlcmd)
        #self.conn.commit()

    def update_schema_22(self):
        cursor = self.conn.cursor()
        sqlcmd = """
        CREATE TABLE run_history (
            scriptname text NOT NULL,
            start_time timestamp with time zone,
            end_time timestamp with time zone,
            pid integer NOT NULL,
            host character varying(64)
        );
        """
        cursor.execute(sqlcmd)
        sqlcmd = "CREATE INDEX run_history_scriptname on run_history (scriptname)"      
        cursor.execute(sqlcmd)
        sqlcmd = "CREATE INDEX run_history_hostpid on run_history (pid,host)"
        cursor.execute(sqlcmd)
        sqlcmd = "create index system_pid on system (pid)"
        cursor.execute(sqlcmd)
        sqlcmd = "create index system_key on system (key);"
        cursor.execute(sqlcmd)

    def _has_table(self,tablename,schemaname="public"):
        cursor = self.conn.cursor()
        sqlcmd = """
        SELECT EXISTS (
            SELECT 1
            FROM   pg_catalog.pg_class c
            JOIN   pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE  n.nspname = %s
            AND    c.relname = %s
            AND    c.relkind = 'r'
        );
        """
        logging.debug("Checking for existence of table {0} in schema {1}".format(tablename,schemaname))
        #logging.debug(sqlcmd)
        cursor.execute(sqlcmd, (schemaname,tablename))
        row = cursor.fetchone()
        return row[0]

    def _has_column(self,tablename,columnname):
        #select column_name from information_schema.columns where table_name='edit_projects' and column_name='clips'
        cursor = self.conn.cursor()
        sqlcmd="select column_name from information_schema.columns where table_name=%s and column_name=%s"
        logging.debug("Checking for existence of column {0} in table {1}".format(tablename,columnname))
        cursor.execute(sqlcmd, (tablename,columnname))
        if cursor.fetchone() is not None:
            return True
        return False

    def check_schema_20(self):
        if not self._has_table('deleted_files'):
            self.update_schema_20()

    def check_schema_21(self):
        if not self._has_column('edit_projects','valid'):
            self.update_schema_21()

    def check_schema_22(self):
        if not self._has_table('run_history'):
            self.update_schema_22()
            self.conn.commit()

    def insert_sysparam(self,key,value):
        cursor=self.conn.cursor()
        for attempt in range(1,10):
            try:
                cursor.execute("insert into system (key,value,pid) values (%s,%s,%s)", (key, value, os.getpid()))
                break
            except psycopg2.InternalError: #if we have an aborted transaction, cleanup and then re-try
                self.conn.rollback()
                continue

    def purge_system_messages(self,since):
        from datetime import timedelta
        if not isinstance(since,timedelta):
            raise TypeError("You need to provide a timedelta to this function")

        timestr = 'P{years}-{months}-{days}'.format(years=0,months=0,days=int(since.days))
        sqlcmd = "delete from system where now()-timestamp > '{0}'".format(timestr)
        #print "sql command is %s" % sqlcmd
        cursor = self.conn.cursor()
        cursor.execute(sqlcmd)

    def commit(self):
        self.conn.commit()

    def cleanuperror(self):
        try:
            self.conn.commit()
        except Exception:
            pass

        self.conn.rollback()

    def pid_for_status(self,statusid,limit=1):
        if not statusid:
            raise ArgumentError("pid_for_status needs a status id")

        cur = self.conn.cursor()
        cur.execute("select pid from system where key='exit' and value='%s' order by timestamp desc limit %s", (statusid,limit))
        for result in cur.fetchall():
            yield result[0]

    def lastrun_endtime(self, status=None):
        return self.lastrun_gettime('run_end', status=status)

    def lastrun_starttime(self, status=None):
        return self.lastrun_gettime('run_start', status=status)

    def lastrun_gettime(self, field, status=None):
        if not self.clientversion:
            raise ArgumentError("Cannot call database::lastrun_endtime without the client name/version string set. Call __init__ properly first.")

        matches = re.search(u'^([\w\d_\-]+)',self.clientversion)
        if matches is None:
            raise ArgumentError("database::lastrun_endtime - Client version string does not provide a script name to search for at the start")

        scriptname = matches.group(1)
        #logging.debug("database::lastrun_endtime - script name determined as %s",scriptname)

        if status is None:
            querystring = "select value from system where key='{0}' and pid=(select pid from system where key='script_version' and value like '{1}%' order by timestamp desc limit 1)".format(field, scriptname)
        else:
            querystring = """select value from system where key='{0}'
                            and pid in (select pid from system where key='script version' and value like '{1}%'
                                and pid in (select pid from system where key='exit' and value='{2}')) limit 1
                        """.format(field,scriptname,status)

        cursor = self.conn.cursor()
        cursor.execute(querystring)
        result = cursor.fetchone()

        if result is None:
            return None #this means that the script is either still running or crashed last time around

        timestamp = dt.datetime.strptime(result[0],"%Y-%m-%dT%H:%M:%S.%f")

        return timestamp

    def mark_id_as_deleted(self, id):
        sqlcmd = """
        insert into deleted_files
        (id,filepath,filename,mtime,ctime,atime,imported_id,imported_at,last_seen,size,owner,gid,prelude_ref,ignore,mime_type)
            select id,filepath,filename,mtime,ctime,atime,imported_id,imported_at,last_seen,size,owner,gid,prelude_ref,ignore,mime_type
            from files
            where id=%s
        """
        cursor=self.conn.cursor()
        cursor.execute(sqlcmd,[id])

        sqlcmd = "update files set prelude_ref=NULL where id=%s"
        cursor.execute(sqlcmd,[id])

        sqlcmd = "delete from prelude_clips where file_reference=%s"
        cursor.execute(sqlcmd,[id])

        sqlcmd = "delete from edit_project_clips where file_ref=%s"
        cursor.execute(sqlcmd,[id])

        sqlcmd = "delete from file_meta where file_id=%s"
        cursor.execute(sqlcmd,[id])

        sqlcmd = "delete from sidecar_files where file_ref=%s"
        cursor.execute(sqlcmd,[id])

        sqlcmd = "delete from files cascade where id=%s"
        cursor.execute(sqlcmd,[id])

        self.conn.commit()

    def start_run(self,scriptname):
        import socket
        self.insert_sysparam('running_host',platform.node())
        self.insert_sysparam('script_version',self.clientversion)
        self.insert_sysparam('python_version',platform.python_version())
        self.insert_sysparam('OS',platform.system())
        self.insert_sysparam('OS_release',platform.release())
        self.insert_sysparam('OS_version',platform.version())
        self.insert_sysparam('run_start',dt.datetime.now().isoformat('T'))
        cursor = self.conn.cursor()

        cursor.execute("insert into run_history (scriptname,start_time,pid,host) values (%s,%s,%s,%s)",
                       (scriptname,dt.datetime.now().isoformat('T'),os.getpid(),socket.gethostname()))
        self.conn.commit()

    def end_run(self,status=None):
        import socket
        self.insert_sysparam('run_end',dt.datetime.now().isoformat('T'))
        if status is not None:
            self.insert_sysparam('exit',status)
        cursor=self.conn.cursor()
        cursor.execute("update run_history set end_time=%s where pid=%s and host=%s",
                       (dt.datetime.now().isoformat('T'),os.getpid(),socket.gethostname()))
        self.conn.commit()

    def project_type_for_extension(self,xtn,desc=None,opens_with=None):
        cursor = self.conn.cursor()

        cursor.execute("select id from edit_project_types where extension='%s'" % xtn)
        result=cursor.fetchone()

        if result is None:
            cursor.execute("insert into edit_project_types (extension,description,opens_with) values (%s,%s,%s) returning id", (xtn,desc,opens_with))
            result=cursor.fetchone()

        id=result[0]

        return id

    def upsert_edit_project(self,filepath,filename,uuid,version,desc=None,opens_with=None):
        cursor = self.conn.cursor()

        matches=re.search(u'(\.[^\.]+)$',filename)
        file_xtn=""
        if matches is not None:
            file_xtn=str(matches.group(1))
        else:
            raise ArgumentError("Filename %s does not appear to have a file extension" % filename)

        typenum=self.project_type_for_extension(file_xtn,desc=desc,opens_with=opens_with)

        try:
            cursor.execute("insert into edit_projects (filename,filepath,type,lastseen,valid) values (%s,%s,%s,now(),true) returning id", (filename,filepath,typenum))
        except psycopg2.IntegrityError as e:
            self.conn.rollback()
            cursor.execute("update edit_projects set lastseen=now(), valid=true where filename=%s and filepath=%s returning id", (filename,filepath))

        result = cursor.fetchone()
        id = result[0]

        sqlcmd="update edit_projects set uuid=%s, version=%s where id=%s"
        cursor.execute(sqlcmd, (uuid,version,id))
        self.conn.commit()
        return id

    def log_project_issue(self,filepath,filename,problem="",detail="",desc=None,opens_with=None):
        cursor = self.conn.cursor()

        matches=re.search(u'(\.[^\.]+)$',filename)
        file_xtn = ""
        if matches is not None:
            file_xtn=str(matches.group(1))
        else:
            raise ArgumentError("Filename %s does not appear to have a file extension" % filename)

        typenum=self.project_type_for_extension(file_xtn,desc=desc,opens_with=opens_with)

        try:
            cursor.execute("""insert into edit_projects (filename,filepath,type,problem,problem_detail,lastseen,valid)
            values (%s,%s,%s,%s,%s,now(),false) returning id""", (filename,filepath,typenum,problem,detail))
        except psycopg2.IntegrityError as e:
            print str(e)
            print traceback.format_exc()
            self.conn.rollback()
            cursor.execute("""update edit_projects set lastseen=now(), valid=false, problem=%s, problem_detail=%s where filename=%s and filepath=%s returning id""", (problem,detail,filename,filepath))
        #print cursor.mogrify("""update edit_projects set lastseen=now(), valid=false, problem=%s, problem_detail=%s where filename=%s and filepath=%s returning id""", (problem,detail,filename,filepath))
        result=cursor.fetchone()
        id = result[0]
        self.conn.commit()
        return id

    def link_file_to_edit_project(self,fileid,projectid):
        cursor=self.conn.cursor()

        cursor.execute("select count(id) from edit_project_clips where file_ref=%s and project_ref=%s", (fileid,projectid))
        result=cursor.fetchone()

        if result[0]>0:
            raise AlreadyLinkedError("File id %s is already linked to project %s" % (fileid,projectid))

        cursor.execute("insert into edit_project_clips (file_ref,project_ref) values (%s,%s)", (fileid,projectid))

    def update_file_record_gone(self,filepath,filename):
        cursor = self.conn.cursor()
        self.conn.commit()

        try:
            cursor.execute("update files set ignore=true where filename=%s and filepath=%s", (filename, filepath))
        except Exception as e:
            logging.warning("Unable to update to ignore gone file: %s" % str(e))
            self.insert_sysparam("warning",str(e))

    def upsert_file_record(self,filepath,filename,statinfo,mimetype,ignore=None):
        cursor=self.conn.cursor()
        self.conn.commit()
        safe_filepath = filepath.decode('utf-8', 'strict')
        safe_filename = filename.decode('utf-8', 'strict')
        try:
            cursor.execute("insert into files (filename,filepath,last_seen) values (%s,%s,now()) returning id", (safe_filename,safe_filepath))
        except psycopg2.IntegrityError as e:
            self.conn.rollback()
            cursor.execute("update files set last_seen=now() where filename=%s and filepath=%s returning id,ignore", (safe_filename, safe_filepath))

        result=cursor.fetchone()
        id=result[0]
        try:
            if result[1] == True:
                ignore = True
        except Exception as e:
            logging.warning("An error occurred: " + str(e) + " trying to get ignore flag")

        sqlcmd="update files set mtime={mt}, atime={at}, ctime={ct}, size=%s, owner=%s, gid=%s, mime_type=%s where id=%s".format(
            mt="(SELECT TIMESTAMP WITH TIME ZONE 'epoch' + "+str(statinfo.st_mtime)+" * INTERVAL '1 second')",
            at="(SELECT TIMESTAMP WITH TIME ZONE 'epoch' + "+str(statinfo.st_atime)+" * INTERVAL '1 second')",
            ct="(SELECT TIMESTAMP WITH TIME ZONE 'epoch' + "+str(statinfo.st_ctime)+" * INTERVAL '1 second')",
        )
        cursor.execute(sqlcmd, (statinfo.st_size,statinfo.st_uid,statinfo.st_gid,mimetype,id))

        if ignore is not None:
            cursor.execute("update files set ignore={ign} where id={id}".format(
                ign=ignore,
                id=id
            ))
        self.conn.commit()

    def fileRecord(self,path):
        cursor=self.conn.cursor()

        #FIXME: this should be separated out into a seperate path mapping object, maybe inside config
        path = re.sub(u'^/Volumes','/srv',path)

        cursor.execute("select * from files where filepath=%s and filename=%s",(os.path.dirname(path),os.path.basename(path)))
        fields = map(lambda x: x[0], cursor.description)
        result=cursor.fetchone()

        if result:
            return dict(zip(fields,result))
        return None

    def get_vidispine_id(self, path):
        cursor = self.conn.cursor()

        cursor.execute("select imported_id from files where filepath=%s and filename=%s",(os.path.dirname(path),os.path.basename(path)))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

    def fileId(self,path):
        cursor=self.conn.cursor()

        #FIXME: this should be separated out into a seperate path mapping object, maybe inside config
        path = re.sub(u'^/Volumes','/srv',path)

        cursor.execute("select id from files where filepath=%s and filename=%s",(os.path.dirname(path),os.path.basename(path)))
        result=cursor.fetchone()

        if result:
            return result[0]
        return None

    def filesForVSID(self,vsid=None,showIgnore=False):
        queryAppend = " and ignore!=TRUE"
        if showIgnore==True:
            queryAppend = ""
        if vsid is not None:
            sqlcmd = "select * from files where imported_id='{0}'{1}".format(vsid,queryAppend)
        else:
            sqlcmd = "select * from files where imported_id is NULL" + queryAppend

        print "About to run %s" %sqlcmd

        cursor=self.conn.cursor()
        cursor.execute(sqlcmd)

        fields = map(lambda x: x[0], cursor.description)

        for result in cursor:
            yield dict(zip(fields,result))

    #since should be a datetime object
    def files(self,since=None,pathspec=None,namespec=None,reverse_order=False):
        sql_params = []

        if since:
            try:
                sql_params.append("lastseen > '"+since.isoformat('T')+"'")
            except Exception as e:
                print "Warning: importer_db::files: %s. 'since' argument is ignored." % e

        if pathspec:
            sql_params.append("filepath like '%{path}%'".format(path=pathspec))

        if namespec:
            sql_params.append("filename like '%{name}%'".format(name=namespec))

        sqlcmd="select * from files "
        if len(sql_params) >0:
            sqlcmd+="where "
            for arg in sql_params:
                sqlcmd+=arg+" "

        sqlcmd+="order by ctime "
        if reverse_order:
            sqlcmd+="desc"
        else:
            sqlcmd+="asc"

        cursor=self.conn.cursor()
        cursor.execute(sqlcmd)
        #http://stackoverflow.com/questions/5010042/mysql-get-column-name-or-alias-from-query
        fields = map(lambda x: x[0], cursor.description)

        for row in cursor:
            entity = dict(zip(fields, row))  #should return a dict with the column names as keys and data as values
            yield entity

    def update_file_ignore(self,fileid,ignflag):
        cursor=self.conn.cursor()

        if not isinstance(fileid,long) and not isinstance(fileid,int):
            raise ArgumentError("fileid argument must be an integer")
        if ignflag:
            cursor.execute("update files set ignore=TRUE where id=%d" % fileid)
        else:
            cursor.execute("update files set ignore=FALSE where id=%d" % fileid)

    def update_file_vidispine_id(self,fileid,vsid):
        cursor=self.conn.cursor()

        if not isinstance(fileid,long) and not isinstance(fileid,int):
            raise ArgumentError("fileid argument must be an integer")

        if not re.match(u'^\w{2}-\d+',vsid):
            msg="Vidispine id {0} does not look like an integer".format(vsid)
            raise ArgumentError(msg)

        cursor.execute("update files set imported_id='{0}',imported_at=now() where id={1}".format(vsid,fileid))

    def upsert_prelude_project(self,path=None,filename=None,uuid=None,version=None,nclips=None):
        cursor=self.conn.cursor()
        self.conn.commit()

        #if uuid is None:
        #    raise DataError("You need to pass a valid uuid")

        try:
            sqlcmd = """insert into prelude_projects (filepath,filename,uuid,version,clips,lastseen)
                        values (%s,%s,%s,%s,%s,now()) returning id"""
            cursor.execute(sqlcmd,(path,filename,uuid,version,nclips))
        except psycopg2.IntegrityError as e: #if we violate unique keys, try to update on filename
            self.conn.rollback()
            try:
                sqlcmd = """update prelude_projects set filepath=%s, filename=%s, uuid=%s, version=%s, clips=%s, lastseen=now()
                            where filepath=%s and filename=%s returning id"""
                cursor.execute(sqlcmd,(path,filename,uuid,version,nclips,path,filename))
            except psycopg2.IntegrityError as e: #if that causes a violation, try to update on uuid
                self.conn.rollback()
                sqlcmd = """update prelude_projects set filepath=%s, filename=%s, uuid=%s, version=%s, clips=%s, lastseen=now()
                            where uuid=%s returning id"""
                cursor.execute(sqlcmd,(path,filename,uuid,version,nclips,uuid))

        self.conn.commit()
        result=cursor.fetchone()
        return result[0]    #return id of inserted row

    def update_project_nclips(self,nclips, projectid=None):
        cursor=self.conn.cursor()
        cursor.execute("update prelude_projects set clips=%s where id=%s",(nclips,projectid))

    def upsert_prelude_clip(self,project_ref=None,asset_name=None,asset_relink_skipped=None,asset_type=None,
            uuid=None,created_date=None,drop_frame=None,duration=None,file_path=None,frame_rate=None,
            import_date=None,parent_uuid=None,start_time=None):
        cursor=self.conn.cursor()

        self.conn.commit()

        try:
            sqlcmd="""insert into prelude_clips (asset_name,asset_relink_skipped,asset_type,class_id,created_date,drop_frame,
            duration_text,file_path,frame_rate,import_date,project,start_time,parent_id)
            values
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id
            """

            cursor.execute(sqlcmd, (asset_name,asset_relink_skipped,asset_type,uuid,created_date,drop_frame,duration,file_path,
            frame_rate,import_date,parent_uuid,start_time,project_ref))

        except psycopg2.IntegrityError as e:
            #if e.startswith('duplicate key'):
            self.conn.rollback()
            sqlcmd = """update prelude_clips set
            asset_name=%s,
            asset_relink_skipped=%s,
            asset_type=%s,
            created_date=%s,
            drop_frame=%s,
            duration_text=%s,
            frame_rate=%s,
            import_date=%s,
            project=%s,
            start_time=%s,
            parent_id=%s
            where class_id=%s and file_path=%s returning id"""

            cursor.execute(sqlcmd,(asset_name,asset_relink_skipped,asset_type,created_date,drop_frame,duration,
            frame_rate,import_date,parent_uuid,start_time,project_ref,uuid,file_path))

        self.conn.commit()
        result=cursor.fetchone()
        return result[0]

    def get_prelude_data(self,preludeid):
        if preludeid is None:
            return None

        if not isinstance(preludeid,int):
            raise ArgumentError("Prelude ID must be an integer that identifies the record in the asset_folrder_importer database")

        cursor=self.conn.cursor()
        cursor.execute("select * from prelude_clips where id={0}".format(preludeid))

        fields = map(lambda x: x[0], cursor.description)

        row=cursor.fetchone()
        if row is None:
            return None

        return dict(zip(fields,row))

    def get_prelude_project(self,projid):
        if not isinstance(projid,int):
            raise ArgumentError("Project ID must be an integer that identifies the record in the asset_folrder_importer database")

        cursor=self.conn.cursor()
        cursor.execute("select * from prelude_projects where id={0}".format(projid))

        fields = map(lambda x: x[0], cursor.description)

        row=cursor.fetchone()

        return dict(zip(fields,row))

    def update_prelude_clip_fileref(self,preludeid,fileid):
        cursor=self.conn.cursor()

        logging.debug("updating prelude clip %s with id %s" % (preludeid,fileid))
        cursor.execute("update prelude_clips set file_reference=%s where id=%s", (fileid,preludeid))
        cursor.execute("update files set prelude_ref=%s where id=%s", (preludeid,fileid))

    def add_sidecar_ref(self,fileid,sidecar_path):
        (sidecar_dir,sidecar_name)=os.path.split(sidecar_path)
        logging.debug("Data used in add_sidecar_ref: fileid = {0} sidecar_dir = {1} sidecar_name = {2}".format(fileid,sidecar_dir,sidecar_name))
        self.conn.commit()
        try:
            cursor=self.conn.cursor()
            cursor.execute("insert into sidecar_files (file_ref,sidecar_path,sidecar_name) values (%s,%s,%s)", (fileid,sidecar_dir,sidecar_name))
        except:
            print "Unable to update sidecar table"
            self.conn.rollback()
            raise StandardError("Debug: sidecar update failed")
