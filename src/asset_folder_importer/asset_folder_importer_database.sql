--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

--
-- Name: upsert_file(text, text); Type: FUNCTION; Schema: public; Owner: assetimporter
--

CREATE FUNCTION upsert_file(fp text, fn text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
        $$;


ALTER FUNCTION public.upsert_file(fp text, fn text) OWNER TO assetimporter;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: file_meta; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE file_meta (
    id integer NOT NULL,
    file_id integer NOT NULL,
    key text,
    value text
);


ALTER TABLE public.file_meta OWNER TO postgres;

--
-- Name: file_meta_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE file_meta_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.file_meta_id_seq OWNER TO postgres;

--
-- Name: file_meta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE file_meta_id_seq OWNED BY file_meta.id;


--
-- Name: files; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE files (
    id integer NOT NULL,
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


ALTER TABLE public.files OWNER TO postgres;

--
-- Name: files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.files_id_seq OWNER TO postgres;

--
-- Name: files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE files_id_seq OWNED BY files.id;


--
-- Name: prelude_clips; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE prelude_clips (
    id integer NOT NULL,
    asset_name text,
    asset_relink_skipped boolean,
    asset_type text,
    class_id uuid,
    created_date timestamp without time zone,
    drop_frame text,
    duration_text character varying(32),
    file_path text NOT NULL,
    frame_rate bigint,
    import_date timestamp without time zone,
    project uuid,
    start_time bigint,
    file_reference bigint,
    parent_id integer
);


ALTER TABLE public.prelude_clips OWNER TO postgres;

--
-- Name: prelude_clips_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE prelude_clips_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.prelude_clips_id_seq OWNER TO postgres;

--
-- Name: prelude_clips_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE prelude_clips_id_seq OWNED BY prelude_clips.id;


--
-- Name: prelude_projects; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE prelude_projects (
    id integer NOT NULL,
    filepath text NOT NULL,
    filename text NOT NULL,
    uuid uuid,
    version text,
    clips integer,
    lastseen timestamp with time zone DEFAULT now()
);


ALTER TABLE public.prelude_projects OWNER TO postgres;

--
-- Name: prelude_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE prelude_projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.prelude_projects_id_seq OWNER TO postgres;

--
-- Name: prelude_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE prelude_projects_id_seq OWNED BY prelude_projects.id;


--
-- Name: sidecar_files; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE sidecar_files (
    id integer NOT NULL,
    file_ref integer,
    sidecar_path text,
    sidecar_name text
);


ALTER TABLE public.sidecar_files OWNER TO postgres;

--
-- Name: sidecar_files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE sidecar_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sidecar_files_id_seq OWNER TO postgres;

--
-- Name: sidecar_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE sidecar_files_id_seq OWNED BY sidecar_files.id;


--
-- Name: system; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE system (
    id integer NOT NULL,
    key text,
    value text,
    "timestamp" timestamp with time zone DEFAULT now(),
    pid integer
);


ALTER TABLE public.system OWNER TO postgres;

--
-- Name: system_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE system_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_id_seq OWNER TO postgres;

--
-- Name: system_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE system_id_seq OWNED BY system.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY file_meta ALTER COLUMN id SET DEFAULT nextval('file_meta_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY files ALTER COLUMN id SET DEFAULT nextval('files_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY prelude_clips ALTER COLUMN id SET DEFAULT nextval('prelude_clips_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY prelude_projects ALTER COLUMN id SET DEFAULT nextval('prelude_projects_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY sidecar_files ALTER COLUMN id SET DEFAULT nextval('sidecar_files_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY system ALTER COLUMN id SET DEFAULT nextval('system_id_seq'::regclass);


--
-- Name: file_meta_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY file_meta
    ADD CONSTRAINT file_meta_pkey PRIMARY KEY (id);


--
-- Name: files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- Name: prelude_clip_unique_key; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY prelude_clips
    ADD CONSTRAINT prelude_clip_unique_key UNIQUE (class_id, file_path);


--
-- Name: prelude_clips_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY prelude_clips
    ADD CONSTRAINT prelude_clips_pkey PRIMARY KEY (id);


--
-- Name: prelude_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY prelude_projects
    ADD CONSTRAINT prelude_projects_pkey PRIMARY KEY (id);


--
-- Name: prelude_projects_unique_filepath; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY prelude_projects
    ADD CONSTRAINT prelude_projects_unique_filepath UNIQUE (filepath, filename);


--
-- Name: system_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY system
    ADD CONSTRAINT system_pkey PRIMARY KEY (id);


--
-- Name: unique_filepath; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY files
    ADD CONSTRAINT unique_filepath UNIQUE (filepath, filename);


--
-- Name: filepath_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX filepath_index ON files USING btree (filepath, filename);


--
-- Name: prelude_clip_assetname_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX prelude_clip_assetname_index ON prelude_clips USING btree (asset_name);


--
-- Name: prelude_clip_assettype_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX prelude_clip_assettype_index ON prelude_clips USING btree (asset_type);


--
-- Name: prelude_clip_filepath_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX prelude_clip_filepath_index ON prelude_clips USING btree (file_path);


--
-- Name: prelude_clip_fileref_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX prelude_clip_fileref_index ON prelude_clips USING btree (file_reference);


--
-- Name: prelude_clip_parent_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX prelude_clip_parent_index ON prelude_clips USING btree (project);


--
-- Name: prelude_projects_filepath_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE UNIQUE INDEX prelude_projects_filepath_index ON prelude_projects USING btree (filepath, filename);


--
-- Name: sidecar_fileref_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX sidecar_fileref_index ON sidecar_files USING btree (file_ref);


--
-- Name: sidecar_fullpath_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX sidecar_fullpath_index ON sidecar_files USING btree (sidecar_path, sidecar_name);


--
-- Name: vsid_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX vsid_index ON files USING btree (imported_id);


--
-- Name: file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY file_meta
    ADD CONSTRAINT file_id_fkey FOREIGN KEY (file_id) REFERENCES files(id);


--
-- Name: files_prelude_ref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY files
    ADD CONSTRAINT files_prelude_ref_fkey FOREIGN KEY (prelude_ref) REFERENCES prelude_clips(id);


--
-- Name: prelude_clip_fileref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY prelude_clips
    ADD CONSTRAINT prelude_clip_fileref_fkey FOREIGN KEY (file_reference) REFERENCES files(id);


--
-- Name: prelude_clip_parent_project_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY prelude_clips
    ADD CONSTRAINT prelude_clip_parent_project_fkey FOREIGN KEY (parent_id) REFERENCES prelude_projects(id);


--
-- Name: sidecar_fileref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY sidecar_files
    ADD CONSTRAINT sidecar_fileref_fkey FOREIGN KEY (file_ref) REFERENCES files(id);


--
-- Name: public; Type: ACL; Schema: -; Owner: assetimporter
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM assetimporter;
GRANT ALL ON SCHEMA public TO assetimporter;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: file_meta; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE file_meta FROM PUBLIC;
REVOKE ALL ON TABLE file_meta FROM postgres;
GRANT ALL ON TABLE file_meta TO postgres;
GRANT SELECT,INSERT,REFERENCES,DELETE,UPDATE ON TABLE file_meta TO assetimporter;


--
-- Name: file_meta_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE file_meta_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE file_meta_id_seq FROM postgres;
GRANT ALL ON SEQUENCE file_meta_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE file_meta_id_seq TO assetimporter;


--
-- Name: files; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE files FROM PUBLIC;
REVOKE ALL ON TABLE files FROM postgres;
GRANT ALL ON TABLE files TO postgres;
GRANT SELECT,INSERT,REFERENCES,DELETE,UPDATE ON TABLE files TO assetimporter;


--
-- Name: files_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE files_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE files_id_seq FROM postgres;
GRANT ALL ON SEQUENCE files_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE files_id_seq TO assetimporter;


--
-- Name: prelude_clips; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE prelude_clips FROM PUBLIC;
REVOKE ALL ON TABLE prelude_clips FROM postgres;
GRANT ALL ON TABLE prelude_clips TO postgres;
GRANT SELECT,INSERT,REFERENCES,DELETE,UPDATE ON TABLE prelude_clips TO assetimporter;


--
-- Name: prelude_clips_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE prelude_clips_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE prelude_clips_id_seq FROM postgres;
GRANT ALL ON SEQUENCE prelude_clips_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE prelude_clips_id_seq TO assetimporter;


--
-- Name: prelude_projects; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE prelude_projects FROM PUBLIC;
REVOKE ALL ON TABLE prelude_projects FROM postgres;
GRANT ALL ON TABLE prelude_projects TO postgres;
GRANT SELECT,INSERT,REFERENCES,DELETE,UPDATE ON TABLE prelude_projects TO assetimporter;


--
-- Name: prelude_projects_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE prelude_projects_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE prelude_projects_id_seq FROM postgres;
GRANT ALL ON SEQUENCE prelude_projects_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE prelude_projects_id_seq TO assetimporter;


--
-- Name: sidecar_files; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE sidecar_files FROM PUBLIC;
REVOKE ALL ON TABLE sidecar_files FROM postgres;
GRANT ALL ON TABLE sidecar_files TO postgres;
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE sidecar_files TO assetimporter;


--
-- Name: sidecar_files_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE sidecar_files_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE sidecar_files_id_seq FROM postgres;
GRANT ALL ON SEQUENCE sidecar_files_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE sidecar_files_id_seq TO assetimporter;


--
-- Name: system; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE system FROM PUBLIC;
REVOKE ALL ON TABLE system FROM postgres;
GRANT ALL ON TABLE system TO postgres;
GRANT SELECT,INSERT,REFERENCES,DELETE,UPDATE ON TABLE system TO assetimporter;


--
-- Name: system_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE system_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE system_id_seq FROM postgres;
GRANT ALL ON SEQUENCE system_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE system_id_seq TO assetimporter;


--
-- PostgreSQL database dump complete
--

