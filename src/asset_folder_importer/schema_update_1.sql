--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: edit_project_types; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE edit_project_types (
    id integer NOT NULL,
    description text,
    extension character varying(256) NOT NULL,
    opens_with text
);


ALTER TABLE public.edit_project_types OWNER TO postgres;

--
-- Name: edit_project_types_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE edit_project_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.edit_project_types_id_seq OWNER TO postgres;

--
-- Name: edit_project_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE edit_project_types_id_seq OWNED BY edit_project_types.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_project_types ALTER COLUMN id SET DEFAULT nextval('edit_project_types_id_seq'::regclass);


--
-- Data for Name: edit_project_types; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO edit_project_types VALUES (2, 'Adobe Premiere Project', '.prproj', '/Applications/Adobe Premiere Pro CC 2014/Adobe Premiere Pro CC 2014.app/Contents/MacOS/Adobe Premiere Pro CC 2014');


--
-- Name: edit_project_types_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('edit_project_types_id_seq', 2, true);


--
-- Name: edit_project_type_unique_extension; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_project_types
    ADD CONSTRAINT edit_project_type_unique_extension UNIQUE (extension);


--
-- Name: edit_project_types_extension_key; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_project_types
    ADD CONSTRAINT edit_project_types_extension_key UNIQUE (extension);


--
-- Name: edit_project_types_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_project_types
    ADD CONSTRAINT edit_project_types_pkey PRIMARY KEY (id);


--
-- Name: edit_project_types; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE edit_project_types FROM PUBLIC;
REVOKE ALL ON TABLE edit_project_types FROM postgres;
GRANT ALL ON TABLE edit_project_types TO postgres;
GRANT SELECT,INSERT,UPDATE ON TABLE edit_project_types TO assetimporter;


--
-- Name: edit_project_types_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE edit_project_types_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE edit_project_types_id_seq FROM postgres;
GRANT ALL ON SEQUENCE edit_project_types_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE edit_project_types_id_seq TO assetimporter;


--
-- PostgreSQL database dump complete
--

--
-- PostgreSQL database dump
--
--
-- Name: edit_projects; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE edit_projects (
    id integer NOT NULL,
    type integer NOT NULL,
    filepath text NOT NULL,
    filename text NOT NULL,
    uuid uuid,
    version text,
    clips integer,
    lastseen timestamp with time zone
);


ALTER TABLE public.edit_projects OWNER TO postgres;

--
-- Name: edit_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE edit_projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.edit_projects_id_seq OWNER TO postgres;

--
-- Name: edit_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE edit_projects_id_seq OWNED BY edit_projects.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_projects ALTER COLUMN id SET DEFAULT nextval('edit_projects_id_seq'::regclass);


--
-- Name: edit_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_projects_pkey PRIMARY KEY (id);


--
-- Name: edit_projects_unique_filepath; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_projects_unique_filepath UNIQUE (filepath, filename);


--
-- Name: edit_project_type_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_projects
    ADD CONSTRAINT edit_project_type_fkey FOREIGN KEY (type) REFERENCES edit_project_types(id);


--
-- Name: edit_projects; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE edit_projects FROM PUBLIC;
REVOKE ALL ON TABLE edit_projects FROM postgres;
GRANT ALL ON TABLE edit_projects TO postgres;
GRANT SELECT,INSERT,UPDATE ON TABLE edit_projects TO assetimporter;


--
-- Name: edit_projects_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE edit_projects_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE edit_projects_id_seq FROM postgres;
GRANT ALL ON SEQUENCE edit_projects_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE edit_projects_id_seq TO assetimporter;


--
-- PostgreSQL database dump complete
--


--
-- Name: edit_project_clips; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE edit_project_clips (
    id integer NOT NULL,
    file_ref integer NOT NULL,
    project_ref integer NOT NULL
);


ALTER TABLE public.edit_project_clips OWNER TO postgres;

--
-- Name: edit_project_clips_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE edit_project_clips_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.edit_project_clips_id_seq OWNER TO postgres;

--
-- Name: edit_project_clips_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE edit_project_clips_id_seq OWNED BY edit_project_clips.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_project_clips ALTER COLUMN id SET DEFAULT nextval('edit_project_clips_id_seq'::regclass);


--
-- Name: edit_project_clips_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY edit_project_clips
    ADD CONSTRAINT edit_project_clips_pkey PRIMARY KEY (id);


--
-- Name: edit_project_clips_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX edit_project_clips_index ON edit_project_clips USING btree (file_ref);


--
-- Name: edit_project_clips_project_index; Type: INDEX; Schema: public; Owner: postgres; Tablespace: 
--

CREATE INDEX edit_project_clips_project_index ON edit_project_clips USING btree (project_ref);


--
-- Name: edit_project_file_ref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_project_clips
    ADD CONSTRAINT edit_project_file_ref_fkey FOREIGN KEY (file_ref) REFERENCES files(id);


--
-- Name: edit_project_project_ref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY edit_project_clips
    ADD CONSTRAINT edit_project_project_ref_fkey FOREIGN KEY (project_ref) REFERENCES edit_projects(id);


--
-- Name: edit_project_clips; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON TABLE edit_project_clips FROM PUBLIC;
REVOKE ALL ON TABLE edit_project_clips FROM postgres;
GRANT ALL ON TABLE edit_project_clips TO postgres;
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE edit_project_clips TO assetimporter;


--
-- Name: edit_project_clips_id_seq; Type: ACL; Schema: public; Owner: postgres
--

REVOKE ALL ON SEQUENCE edit_project_clips_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE edit_project_clips_id_seq FROM postgres;
GRANT ALL ON SEQUENCE edit_project_clips_id_seq TO postgres;
GRANT SELECT,UPDATE ON SEQUENCE edit_project_clips_id_seq TO assetimporter;


--
-- PostgreSQL database dump complete
--


