--
-- PostgreSQL database dump
--

\restrict lANdggfEm7uFYc62JtmdmoscmOXWW2KYFuElTvwLEe4ZhR7jyczWaOzvfqiR1uN

-- Dumped from database version 16.11 (Homebrew)
-- Dumped by pg_dump version 16.11 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: catalog; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA catalog;


--
-- Name: crm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA crm;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: camp_admin_accounts; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.camp_admin_accounts (
    id integer NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    display_name text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: camp_admin_accounts_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.camp_admin_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: camp_admin_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.camp_admin_accounts_id_seq OWNED BY auth.camp_admin_accounts.id;


--
-- Name: user_events; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.user_events (
    id integer NOT NULL,
    user_id integer NOT NULL,
    event_type text NOT NULL,
    payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_events_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.user_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_events_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.user_events_id_seq OWNED BY auth.user_events.id;


--
-- Name: user_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.user_tokens (
    token text NOT NULL,
    user_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked boolean DEFAULT false NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    id integer NOT NULL,
    name text,
    phone text,
    role text,
    email text,
    phone_verified boolean DEFAULT false NOT NULL,
    email_verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    terms_accepted_at timestamp with time zone,
    terms_version text
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.users_id_seq OWNED BY auth.users.id;


--
-- Name: camp_photos; Type: TABLE; Schema: catalog; Owner: -
--

CREATE TABLE catalog.camp_photos (
    id integer NOT NULL,
    camp_id integer,
    url text,
    sort integer,
    cover integer
);


--
-- Name: camp_photos_id_seq; Type: SEQUENCE; Schema: catalog; Owner: -
--

CREATE SEQUENCE catalog.camp_photos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: camp_photos_id_seq; Type: SEQUENCE OWNED BY; Schema: catalog; Owner: -
--

ALTER SEQUENCE catalog.camp_photos_id_seq OWNED BY catalog.camp_photos.id;


--
-- Name: camps; Type: TABLE; Schema: catalog; Owner: -
--

CREATE TABLE catalog.camps (
    id integer NOT NULL,
    name text,
    lat double precision,
    lng double precision,
    min_price integer,
    emoji text,
    lake_name text,
    photo_main text,
    status text,
    owner text,
    manager text,
    admin_phones text,
    rooms_count integer,
    beds_count integer,
    address text,
    phone text,
    site_url text,
    emoji_size text,
    bbq_count integer,
    bbq_shared_count integer,
    bath_count integer,
    sauna_count integer,
    pools_private_count integer,
    pools_shared_count integer,
    description text,
    housing_type text DEFAULT 'apartments'::text NOT NULL
);


--
-- Name: camps_id_seq; Type: SEQUENCE; Schema: catalog; Owner: -
--

CREATE SEQUENCE catalog.camps_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: camps_id_seq; Type: SEQUENCE OWNED BY; Schema: catalog; Owner: -
--

ALTER SEQUENCE catalog.camps_id_seq OWNED BY catalog.camps.id;


--
-- Name: room_photos; Type: TABLE; Schema: catalog; Owner: -
--

CREATE TABLE catalog.room_photos (
    id integer NOT NULL,
    camp_id integer NOT NULL,
    room_id integer NOT NULL,
    url text NOT NULL,
    cover integer DEFAULT 0,
    sort integer DEFAULT 0
);


--
-- Name: room_photos_id_seq; Type: SEQUENCE; Schema: catalog; Owner: -
--

CREATE SEQUENCE catalog.room_photos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: room_photos_id_seq; Type: SEQUENCE OWNED BY; Schema: catalog; Owner: -
--

ALTER SEQUENCE catalog.room_photos_id_seq OWNED BY catalog.room_photos.id;


--
-- Name: rooms; Type: TABLE; Schema: catalog; Owner: -
--

CREATE TABLE catalog.rooms (
    id integer NOT NULL,
    camp_id integer,
    name text,
    room_type text,
    floors integer,
    floor integer,
    beds_single integer,
    beds_double integer,
    wc_count integer,
    bath_type text,
    has_ac integer,
    has_bbq integer,
    has_kitchen integer,
    capacity integer,
    price integer,
    photo_main text,
    photos_json text,
    description text,
    price_adult integer,
    price_child integer,
    discount_pct integer,
    discount_from_nights integer,
    wc_type text,
    bbq_type text,
    kitchen_type text,
    gazebo_type text,
    terrace_type text,
    balcony_type text,
    pool_type text
);


--
-- Name: rooms_id_seq; Type: SEQUENCE; Schema: catalog; Owner: -
--

CREATE SEQUENCE catalog.rooms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rooms_id_seq; Type: SEQUENCE OWNED BY; Schema: catalog; Owner: -
--

ALTER SEQUENCE catalog.rooms_id_seq OWNED BY catalog.rooms.id;


--
-- Name: admins; Type: TABLE; Schema: crm; Owner: -
--

CREATE TABLE crm.admins (
    id integer NOT NULL,
    user_id integer,
    camp_id integer,
    role text,
    created_at timestamp with time zone
);


--
-- Name: admins_id_seq; Type: SEQUENCE; Schema: crm; Owner: -
--

CREATE SEQUENCE crm.admins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admins_id_seq; Type: SEQUENCE OWNED BY; Schema: crm; Owner: -
--

ALTER SEQUENCE crm.admins_id_seq OWNED BY crm.admins.id;


--
-- Name: bookings; Type: TABLE; Schema: crm; Owner: -
--

CREATE TABLE crm.bookings (
    id integer NOT NULL,
    user_id integer,
    camp_id integer,
    room_id integer,
    group_id text,
    check_in date,
    check_out date,
    guests_count integer,
    status text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    source text DEFAULT 'crm'::text NOT NULL,
    comment text,
    payment_status text DEFAULT 'unpaid'::text NOT NULL,
    payment_required boolean DEFAULT false NOT NULL,
    guest_name text,
    guest_phone text,
    guest_email text
);


--
-- Name: bookings_id_seq; Type: SEQUENCE; Schema: crm; Owner: -
--

CREATE SEQUENCE crm.bookings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bookings_id_seq; Type: SEQUENCE OWNED BY; Schema: crm; Owner: -
--

ALTER SEQUENCE crm.bookings_id_seq OWNED BY crm.bookings.id;


--
-- Name: camp_admin_links; Type: TABLE; Schema: crm; Owner: -
--

CREATE TABLE crm.camp_admin_links (
    id integer NOT NULL,
    admin_id integer NOT NULL,
    camp_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: camp_admin_links_id_seq; Type: SEQUENCE; Schema: crm; Owner: -
--

CREATE SEQUENCE crm.camp_admin_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: camp_admin_links_id_seq; Type: SEQUENCE OWNED BY; Schema: crm; Owner: -
--

ALTER SEQUENCE crm.camp_admin_links_id_seq OWNED BY crm.camp_admin_links.id;


--
-- Name: camp_admin_accounts id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.camp_admin_accounts ALTER COLUMN id SET DEFAULT nextval('auth.camp_admin_accounts_id_seq'::regclass);


--
-- Name: user_events id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_events ALTER COLUMN id SET DEFAULT nextval('auth.user_events_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users ALTER COLUMN id SET DEFAULT nextval('auth.users_id_seq'::regclass);


--
-- Name: camp_photos id; Type: DEFAULT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.camp_photos ALTER COLUMN id SET DEFAULT nextval('catalog.camp_photos_id_seq'::regclass);


--
-- Name: camps id; Type: DEFAULT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.camps ALTER COLUMN id SET DEFAULT nextval('catalog.camps_id_seq'::regclass);


--
-- Name: room_photos id; Type: DEFAULT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.room_photos ALTER COLUMN id SET DEFAULT nextval('catalog.room_photos_id_seq'::regclass);


--
-- Name: rooms id; Type: DEFAULT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.rooms ALTER COLUMN id SET DEFAULT nextval('catalog.rooms_id_seq'::regclass);


--
-- Name: admins id; Type: DEFAULT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.admins ALTER COLUMN id SET DEFAULT nextval('crm.admins_id_seq'::regclass);


--
-- Name: bookings id; Type: DEFAULT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.bookings ALTER COLUMN id SET DEFAULT nextval('crm.bookings_id_seq'::regclass);


--
-- Name: camp_admin_links id; Type: DEFAULT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.camp_admin_links ALTER COLUMN id SET DEFAULT nextval('crm.camp_admin_links_id_seq'::regclass);


--
-- Data for Name: camp_admin_accounts; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.camp_admin_accounts (id, email, password_hash, display_name, is_active, created_at) FROM stdin;
2	test@mail.ru	$pbkdf2-sha256$29000$WAvhvDcGIOR8r7WWsta6dw$w3jPrwndbySQnIYlQJz/JaEyENH9fV1UToeuPfH3Jfs	Тест	t	2025-11-17 21:59:22.420782+03
\.


--
-- Data for Name: user_events; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.user_events (id, user_id, event_type, payload, created_at) FROM stdin;
1	4	login_start	{"phone": "+79465256556"}	2026-01-03 21:28:49.463162+03
2	4	login_ok	{"phone": "+79465256556"}	2026-01-03 21:28:52.630352+03
3	4	login_start	{"phone": "+79465256556"}	2026-01-03 21:48:17.447589+03
4	4	login_ok	{"phone": "+79465256556"}	2026-01-03 21:48:22.264233+03
5	4	logout	{}	2026-01-03 21:48:49.954142+03
6	4	login_start	{"phone": "+79465256556"}	2026-01-03 21:55:40.776322+03
7	4	login_ok	{"phone": "+79465256556"}	2026-01-03 21:55:44.232977+03
8	4	logout	{}	2026-01-03 21:56:16.560273+03
9	4	login_start	{"phone": "+79465256556"}	2026-01-04 17:37:24.929532+03
10	4	login_ok	{"phone": "+79465256556"}	2026-01-04 17:37:29.044479+03
11	4	profile_update	{"name": "Николай Власов", "email": null, "phone": "+79465256556"}	2026-01-04 17:40:47.219686+03
12	4	profile_update	{"name": "Николай Власов", "email": null, "phone": "+79465256556"}	2026-01-04 17:41:26.029126+03
13	4	login_start	{"phone": "+79465256556"}	2026-01-04 17:51:52.682026+03
14	4	login_ok	{"phone": "+79465256556"}	2026-01-04 17:51:55.797733+03
15	4	logout	{}	2026-01-04 18:24:09.476356+03
16	6	register_start	{"name": "Карл Петров", "email": null, "phone": "+79999999999", "accept_terms": true, "terms_version": "2026-01-04"}	2026-01-04 18:25:38.332327+03
17	6	verify_phone	{"phone": "+79999999999"}	2026-01-04 18:25:43.396424+03
18	4	logout	{}	2026-01-04 18:28:33.134024+03
19	4	login_start	{"phone": "+79465256556"}	2026-01-06 17:00:23.802024+03
20	4	login_ok	{"phone": "+79465256556"}	2026-01-06 17:00:26.680855+03
21	6	login_start	{"phone": "+79999999999"}	2026-01-06 19:30:22.007994+03
22	6	login_ok	{"phone": "+79999999999"}	2026-01-06 19:30:24.926416+03
23	4	booking_create	{"camp_id": 1, "room_id": 122, "check_in": "2026-01-12", "check_out": "2026-01-18", "booking_id": 2, "guests_count": 4}	2026-01-06 23:51:46.15276+03
24	4	booking_admin_update	{"status": "rejected", "admin_id": 2, "booking_id": 2, "payment_status": "unpaid", "payment_required": false}	2026-01-07 00:27:15.821449+03
25	6	login_start	{"phone": "+79999999999"}	2026-01-07 19:37:26.454788+03
26	6	login_ok	{"phone": "+79999999999"}	2026-01-07 19:37:31.283994+03
27	6	booking_create	{"camp_id": 2, "room_id": 100, "check_in": "2026-01-12", "check_out": "2026-01-18", "booking_id": 3, "guests_count": 2}	2026-01-07 21:38:22.679586+03
28	6	booking_create	{"camp_id": 2, "room_id": 103, "check_in": "2026-01-12", "check_out": "2026-01-18", "booking_id": 4, "guests_count": 7}	2026-01-07 21:38:22.703175+03
29	6	booking_admin_update	{"status": "confirmed", "admin_id": 2, "booking_id": 3, "payment_status": "unpaid", "payment_required": true}	2026-01-07 21:39:46.733598+03
30	6	booking_admin_update	{"status": "confirmed", "admin_id": 2, "booking_id": 4, "payment_status": "unpaid", "payment_required": true}	2026-01-07 21:39:56.788976+03
31	6	booking_pay_click	{"booking_id": 4}	2026-01-07 21:40:55.752928+03
32	6	booking_create	{"camp_id": 3, "room_id": 107, "check_in": "2026-01-19", "check_out": "2026-01-25", "booking_id": 5, "guests_count": 4}	2026-01-07 21:42:45.336648+03
33	6	booking_admin_update	{"status": "confirmed", "admin_id": 2, "booking_id": 5, "payment_status": "unpaid", "payment_required": true}	2026-01-07 21:43:53.154596+03
34	6	booking_pay_click	{"booking_id": 5}	2026-01-07 21:44:16.166087+03
35	7	register_start	{"name": "Маргарита", "email": null, "phone": "+79834591035", "accept_terms": true, "terms_version": "2026-01-04"}	2026-01-07 21:47:47.017224+03
36	7	verify_phone	{"phone": "+79834591035"}	2026-01-07 21:47:59.611079+03
37	7	booking_create	{"camp_id": 2, "room_id": 101, "check_in": "2026-01-26", "check_out": "2026-01-31", "booking_id": 6, "guests_count": 3}	2026-01-07 21:49:05.810291+03
38	7	booking_admin_update	{"status": "rejected", "admin_id": 2, "booking_id": 6, "payment_status": "unpaid", "payment_required": false}	2026-01-07 21:50:14.826833+03
39	7	logout	{}	2026-01-07 21:53:56.583945+03
40	7	login_start	{"phone": "+79834591035"}	2026-01-07 21:54:07.739899+03
41	7	login_ok	{"phone": "+79834591035"}	2026-01-07 21:54:14.027032+03
42	7	logout	{}	2026-01-07 21:54:22.178143+03
43	6	logout	{}	2026-01-07 21:54:40.690888+03
44	8	register_start	{"name": "Михаил Бекбаев", "email": null, "phone": "+79247577440", "accept_terms": true, "terms_version": "2026-01-04"}	2026-01-08 14:32:21.073758+03
45	8	verify_phone	{"phone": "+79247577440"}	2026-01-08 14:32:38.408312+03
46	8	booking_create	{"camp_id": 2, "room_id": 103, "check_in": "2026-01-09", "check_out": "2026-01-11", "booking_id": 7, "guests_count": 3}	2026-01-08 14:33:24.398997+03
47	8	booking_admin_update	{"status": "confirmed", "admin_id": 2, "booking_id": 7, "payment_status": "unpaid", "payment_required": false}	2026-01-08 14:37:35.768882+03
48	8	booking_admin_update	{"status": "confirmed", "admin_id": 2, "booking_id": 7, "payment_status": "unpaid", "payment_required": true}	2026-01-08 14:37:43.538609+03
49	8	booking_pay_click	{"booking_id": 7}	2026-01-08 14:38:24.310253+03
50	6	booking_admin_update	{"status": "completed", "admin_id": 2, "booking_id": 3, "payment_status": "paid", "payment_required": true}	2026-01-08 14:55:19.168337+03
51	6	booking_admin_update	{"status": "completed", "admin_id": 2, "booking_id": 4, "payment_status": "paid", "payment_required": true}	2026-01-08 14:55:26.387329+03
52	8	booking_admin_update	{"status": "completed", "admin_id": 2, "booking_id": 7, "payment_status": "paid", "payment_required": true}	2026-01-08 14:55:31.78817+03
53	7	booking_admin_update	{"status": "cancelled_by_user", "admin_id": 2, "booking_id": 6, "payment_status": "unpaid", "payment_required": false}	2026-01-08 14:55:38.287007+03
54	6	booking_admin_update	{"status": "completed", "admin_id": 2, "booking_id": 5, "payment_status": "paid", "payment_required": true}	2026-01-08 14:56:08.266376+03
55	6	login_start	{"phone": "+79999999999"}	2026-01-08 14:58:03.878604+03
56	6	login_ok	{"phone": "+79999999999"}	2026-01-08 14:58:06.788032+03
\.


--
-- Data for Name: user_tokens; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.user_tokens (token, user_id, created_at, revoked) FROM stdin;
yip7JfXQGTU_Njjjj-ajLuYOPiNvV-pl	4	2026-01-03 21:28:52.638326+03	f
acODcWw6emnALCSVpPgWD08KrQYkZbQk	4	2026-01-03 21:48:22.272667+03	t
MifLKbRL01twiNCu02DXYKOVRWbgHh14	4	2026-01-03 21:55:44.240655+03	t
4MejK9rAJ-0nPSCFBe2Dd4THbhEp3umR	4	2026-01-04 17:51:55.805246+03	t
EB6XqWfRvpZlLJgSaxC9_TOB7vqUWjYo	6	2026-01-04 18:25:43.404899+03	f
RLi_PTmIvfZwlmqKqOI2_EmYY5l1QimH	4	2026-01-04 17:37:29.052337+03	t
XFabu7fIS2iiLajpZkvInpjUaOEUDg1i	4	2026-01-06 17:00:26.68905+03	f
4o82LXBklG-VkWEsvRMBlTHBQ6ey6l2j	6	2026-01-07 19:37:31.292213+03	f
CrWus3Ets6ZqpIyhHrGqKyoRvHnOErIC	7	2026-01-07 21:47:59.618029+03	t
RTTzZXPSlr__YNjomJ9vZyXNZfi91ArM	7	2026-01-07 21:54:14.034561+03	t
vvF3KKiF6HxbpDUCMmz3Ur9b5y4xBOz5	6	2026-01-06 19:30:24.935632+03	t
Py-ahuSV8Q-aIHee8ZJRjtaThX-S_pdi	8	2026-01-08 14:32:38.415758+03	f
XPwmEPirFrWNFp6T5MCJ8A4sTZdLLT7C	6	2026-01-08 14:58:06.796329+03	f
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.users (id, name, phone, role, email, phone_verified, email_verified, created_at, terms_accepted_at, terms_version) FROM stdin;
1	Иван Петров	+7 900 000-00-00	\N	\N	f	f	2026-01-03 19:41:43.439922+03	\N	\N
2	Семен Семенов	+79122343223	user	233223@bk.ru	t	t	2026-01-03 19:48:49.090295+03	\N	\N
3	Лаврон Погосян	+70963963969	user	name@bk.co	t	t	2026-01-03 19:55:45.07449+03	\N	\N
5	Иван Пахомов	+79879879887	user	\N	t	f	2026-01-03 20:07:53.96+03	\N	\N
4	Николай Власов	+79465256556	user	\N	t	f	2026-01-03 20:02:43.122525+03	\N	\N
6	Карл Петров	+79999999999	user	\N	t	f	2026-01-04 18:25:38.323764+03	2026-01-04 18:25:38.323764+03	2026-01-04
7	Маргарита	+79834591035	user	\N	t	f	2026-01-07 21:47:47.009871+03	2026-01-07 21:47:47.009871+03	2026-01-04
8	Михаил Бекбаев	+79247577440	user	\N	t	f	2026-01-08 14:32:21.063786+03	2026-01-08 14:32:21.063786+03	2026-01-04
\.


--
-- Data for Name: camp_photos; Type: TABLE DATA; Schema: catalog; Owner: -
--

COPY catalog.camp_photos (id, camp_id, url, sort, cover) FROM stdin;
128	2	/static/uploads/2_hayany/20251101-010622750127.jpg	0	1
129	2	/static/uploads/2_hayany/20251101-010622759435.jpg	1	0
130	2	/static/uploads/2_hayany/20251101-010622766432.jpg	2	0
131	3	/static/uploads/3_gostinyy-dvor/20251101-010719668768.jpg	0	1
132	3	/static/uploads/3_gostinyy-dvor/20251101-010719675955.jpg	1	0
133	3	/static/uploads/3_gostinyy-dvor/20251101-010719681681.jpg	2	0
173	1	/static/uploads/1_angir/20260104-205653343757.jpg	0	1
174	1	/static/uploads/1_angir/20260104-205653353342.jpg	1	0
175	1	/static/uploads/1_angir/20260104-205653363172.jpg	2	0
\.


--
-- Data for Name: camps; Type: TABLE DATA; Schema: catalog; Owner: -
--

COPY catalog.camps (id, name, lat, lng, min_price, emoji, lake_name, photo_main, status, owner, manager, admin_phones, rooms_count, beds_count, address, phone, site_url, emoji_size, bbq_count, bbq_shared_count, bath_count, sauna_count, pools_private_count, pools_shared_count, description, housing_type) FROM stdin;
2	Хаяны	51.214718	106.493157	3000	🏡	Гусиное	/static/uploads/2_hayany/20251101-010622750127.jpg	active	Иванов Степан Баирович, +7 999 99 99 99	Батуев Жаргал Харитонович, +7 888 88 88 88	+7 777 77 77 77, +7 777 77 77 88	4	17	Садоводческий кооператив Уголёк, 117, сельское поселение Загустайское, Селенгинский район, Республика Бурятия	\N		vip	2	0	1	1	0	0	Комфортная база отдыха на берегу Гусиного озера для отдыха всей семьей или компанией!🌞	apartments
3	Гостиный Дворъ	52.802339	107.96961	4000	🏕️	Байкал	/static/uploads/3_gostinyy-dvor/20251101-010719668768.jpg	active	Харитонов Игорь Байгалович, +7 980 908 09 89	Шестерной Олег Жаргалович, +7 980 908 09 90	+7 777 77 77 77, +7 777 77 99 99, +7 770 99 07 77	4	13	Микрорайон Байкальский, 39А, село Гремячинск, Прибайкальский район, Республика Бурятия	\N		standard	2	2	2	1	1	1	Уютная гостиница с территорией для отдыха на Байкале для отдыха всей семьей или компанией!🌅	apartments
1	Ангир	51.40615	106.535513	3500	🏖️	Щучье	/static/uploads/1_angir/20260104-205653343757.jpg	active	Жакмыксамбаев Самбула Хатурович, +7 987 087 98 78	Засандаль Картык Блантуевна, +7 989 989 98 65	+7 777 77 77 77, +7 777 77 77 34, +7 777 77 77 23	4	12	Республика Бурятия, Селенгинский район, сельское поселение Загустайское, территория Южное побережье Щучьего озера	\N		standard	1	1	1	1	0	0	Комфортный мотель на Щучьем озере для отдыха всей семьей или компанией!😊	apartments
\.


--
-- Data for Name: room_photos; Type: TABLE DATA; Schema: catalog; Owner: -
--

COPY catalog.room_photos (id, camp_id, room_id, url, cover, sort) FROM stdin;
77	2	100	/static/uploads/2_hayany/2-100_standart/20251101-010636401002.jpg	1	0
78	2	100	/static/uploads/2_hayany/2-100_standart/20251101-010636408295.jpg	0	1
79	2	100	/static/uploads/2_hayany/2-100_standart/20251101-010636415283.jpg	0	2
80	2	101	/static/uploads/2_hayany/2-101_standart/20251101-010644691487.jpg	1	0
81	2	101	/static/uploads/2_hayany/2-101_standart/20251101-010644699204.jpg	0	1
82	2	101	/static/uploads/2_hayany/2-101_standart/20251101-010644705774.jpg	0	2
83	2	102	/static/uploads/2_hayany/2-102_komfort/20251101-010652632735.jpg	1	0
84	2	102	/static/uploads/2_hayany/2-102_komfort/20251101-010652642339.jpg	0	1
85	2	102	/static/uploads/2_hayany/2-102_komfort/20251101-010652650200.jpg	0	2
86	2	103	/static/uploads/2_hayany/2-103_lyuks/20251101-010700292703.jpg	1	0
87	2	103	/static/uploads/2_hayany/2-103_lyuks/20251101-010700300698.jpg	0	1
88	2	103	/static/uploads/2_hayany/2-103_lyuks/20251101-010700315027.jpg	0	2
89	3	104	/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729169592.jpg	1	0
90	3	104	/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729192805.jpg	0	1
91	3	104	/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729215935.jpg	0	2
92	3	105	/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737866987.jpg	1	0
93	3	105	/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737874332.jpg	0	1
94	3	105	/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737881171.jpg	0	2
95	3	106	/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747230905.jpg	0	0
96	3	106	/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747243898.jpg	0	1
97	3	106	/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747255370.jpg	1	2
98	3	107	/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757214888.jpg	0	0
99	3	107	/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757224358.jpg	1	1
100	3	107	/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757241797.jpg	0	2
269	1	120	/static/uploads/1_angir/1-120_standart/20251101-010318486811.jpg	1	0
270	1	120	/static/uploads/1_angir/1-120_standart/20251101-010318495992.jpg	0	1
271	1	120	/static/uploads/1_angir/1-120_standart/20251101-010318505275.jpg	0	2
272	1	121	/static/uploads/1_angir/1-121_standart/20251101-010327243626.jpg	1	0
273	1	121	/static/uploads/1_angir/1-121_standart/20251101-010327252904.jpg	0	1
274	1	121	/static/uploads/1_angir/1-121_standart/20251101-010327261075.jpg	0	2
275	1	122	/static/uploads/1_angir/1-122_komfort/20251101-010339263146.jpg	1	0
276	1	122	/static/uploads/1_angir/1-122_komfort/20251101-010339273103.jpg	0	1
277	1	122	/static/uploads/1_angir/1-122_komfort/20251101-010339279323.jpg	0	2
278	1	123	/static/uploads/1_angir/1-123_lyuks/20251101-010349429903.jpg	1	0
279	1	123	/static/uploads/1_angir/1-123_lyuks/20251101-010349437771.jpg	0	1
280	1	123	/static/uploads/1_angir/1-123_lyuks/20251101-010349445779.jpg	0	2
\.


--
-- Data for Name: rooms; Type: TABLE DATA; Schema: catalog; Owner: -
--

COPY catalog.rooms (id, camp_id, name, room_type, floors, floor, beds_single, beds_double, wc_count, bath_type, has_ac, has_bbq, has_kitchen, capacity, price, photo_main, photos_json, description, price_adult, price_child, discount_pct, discount_from_nights, wc_type, bbq_type, kitchen_type, gazebo_type, terrace_type, balcony_type, pool_type) FROM stdin;
100	2	Стандарт	Дом	1	1	2	0	0		0	0	0	2	0	/static/uploads/2_hayany/2-100_standart/20251101-010636401002.jpg	["/static/uploads/2_hayany/2-100_standart/20251101-010636401002.jpg", "/static/uploads/2_hayany/2-100_standart/20251101-010636408295.jpg", "/static/uploads/2_hayany/2-100_standart/20251101-010636415283.jpg"]	\N	3000	2000	10	3	shared	shared	shared	shared			
101	2	Стандарт	Дом	1	1	1	1	0		0	0	0	3	0	/static/uploads/2_hayany/2-101_standart/20251101-010644691487.jpg	["/static/uploads/2_hayany/2-101_standart/20251101-010644691487.jpg", "/static/uploads/2_hayany/2-101_standart/20251101-010644699204.jpg", "/static/uploads/2_hayany/2-101_standart/20251101-010644705774.jpg"]	\N	3000	2000	10	3	shared	shared	shared	shared			
102	2	Комфорт	Дом	1	1	2	1	0		1	0	0	4	0	/static/uploads/2_hayany/2-102_komfort/20251101-010652632735.jpg	["/static/uploads/2_hayany/2-102_komfort/20251101-010652632735.jpg", "/static/uploads/2_hayany/2-102_komfort/20251101-010652642339.jpg", "/static/uploads/2_hayany/2-102_komfort/20251101-010652650200.jpg"]	\N	5000	3500	10	3	indiv-split	private	private	private			
103	2	Люкс	Дом	2	1	4	2	0	shower	1	0	0	8	0	/static/uploads/2_hayany/2-103_lyuks/20251101-010700292703.jpg	["/static/uploads/2_hayany/2-103_lyuks/20251101-010700292703.jpg", "/static/uploads/2_hayany/2-103_lyuks/20251101-010700300698.jpg", "/static/uploads/2_hayany/2-103_lyuks/20251101-010700315027.jpg"]	\N	7000	6000	10	3	indiv-split	private	private	private	private		
104	3	Стандарт	Номер	2	1	2	0	0	shower-shared	0	0	0	2	0	/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729169592.jpg	["/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729169592.jpg", "/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729192805.jpg", "/static/uploads/3_gostinyy-dvor/3-104_standart/20251101-010729215935.jpg"]	\N	4000	3000	5	3	shared	shared	shared	shared	shared		shared
105	3	Стандарт	Номер	2	1	1	1	0	shower-shared	0	0	0	3	0	/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737866987.jpg	["/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737866987.jpg", "/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737874332.jpg", "/static/uploads/3_gostinyy-dvor/3-105_standart/20251101-010737881171.jpg"]	\N	4000	3000	5	3	shared	shared	shared	shared	shared		shared
106	3	Комфорт	Номер	2	2	0	1	0	shower	1	0	0	2	0	/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747255370.jpg	["/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747230905.jpg", "/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747243898.jpg", "/static/uploads/3_gostinyy-dvor/3-106_komfort/20251101-010747255370.jpg"]	\N	5000	3500	5	3	indiv-combined	private	shared	private		private	shared
107	3	Люкс	Номер	2	2	2	2	0	shower	1	0	0	6	0	/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757224358.jpg	["/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757214888.jpg", "/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757224358.jpg", "/static/uploads/3_gostinyy-dvor/3-107_lyuks/20251101-010757241797.jpg"]	\N	8000	7000	5	3	indiv-split	private	private	private		private	private
121	1	Стандарт	Апартамент	2	1	0	1	0	shower-shared	0	0	0	2	0	/static/uploads/1_angir/1-121_standart/20251101-010327243626.jpg	["/static/uploads/1_angir/1-121_standart/20251101-010327243626.jpg", "/static/uploads/1_angir/1-121_standart/20251101-010327252904.jpg", "/static/uploads/1_angir/1-121_standart/20251101-010327261075.jpg"]		3500	2500	10	3	shared	shared	shared	shared	shared	shared	
120	1	Стандарт	Апартамент	2	1	2	0	0	shower-shared	0	0	0	2	0	/static/uploads/1_angir/1-120_standart/20251101-010318486811.jpg	["/static/uploads/1_angir/1-120_standart/20251101-010318486811.jpg", "/static/uploads/1_angir/1-120_standart/20251101-010318495992.jpg", "/static/uploads/1_angir/1-120_standart/20251101-010318505275.jpg"]		3500	2500	10	3	shared	shared	shared	shared	shared	shared	
122	1	Комфорт	Апартамент	2	1	2	1	0	shower	1	0	0	4	0	/static/uploads/1_angir/1-122_komfort/20251101-010339263146.jpg	["/static/uploads/1_angir/1-122_komfort/20251101-010339263146.jpg", "/static/uploads/1_angir/1-122_komfort/20251101-010339273103.jpg", "/static/uploads/1_angir/1-122_komfort/20251101-010339279323.jpg"]		4500	3500	10	3	indiv-combined	shared	private	private	shared	shared	
123	1	Люкс	Апартамент	2	1	4	0	0	shower	1	0	0	4	0	/static/uploads/1_angir/1-123_lyuks/20251101-010349429903.jpg	["/static/uploads/1_angir/1-123_lyuks/20251101-010349429903.jpg", "/static/uploads/1_angir/1-123_lyuks/20251101-010349437771.jpg", "/static/uploads/1_angir/1-123_lyuks/20251101-010349445779.jpg"]		7000	5000	10	3	indiv-split	private	private	private	shared	shared	
\.


--
-- Data for Name: admins; Type: TABLE DATA; Schema: crm; Owner: -
--

COPY crm.admins (id, user_id, camp_id, role, created_at) FROM stdin;
\.


--
-- Data for Name: bookings; Type: TABLE DATA; Schema: crm; Owner: -
--

COPY crm.bookings (id, user_id, camp_id, room_id, check_in, check_out, guests_count, status, created_at, updated_at, source, comment, payment_status, payment_required, guest_name, guest_phone, guest_email) FROM stdin;
2	4	1	122	2026-01-12	2026-01-18	4	rejected	\N	2026-01-07 00:27:15.810351+03	webapp	\N	unpaid	f	\N	\N	\N
3	6	2	100	2026-01-12	2026-01-18	2	completed	\N	2026-01-08 14:55:19.160945+03	webapp	\N	paid	f	\N	\N	\N
4	6	2	103	2026-01-12	2026-01-18	7	completed	\N	2026-01-08 14:55:26.379607+03	webapp	\N	paid	f	\N	\N	\N
7	8	2	103	2026-01-09	2026-01-11	3	completed	\N	2026-01-08 14:55:31.77998+03	webapp	\N	paid	f	\N	\N	\N
6	7	2	101	2026-01-26	2026-01-31	3	cancelled_by_user	\N	2026-01-08 14:55:38.280762+03	webapp	\N	unpaid	f	\N	\N	\N
5	6	3	107	2026-01-19	2026-01-25	4	completed	\N	2026-01-08 14:56:08.260142+03	webapp	\N	paid	f	\N	\N	\N
\.


--
-- Data for Name: camp_admin_links; Type: TABLE DATA; Schema: crm; Owner: -
--

COPY crm.camp_admin_links (id, admin_id, camp_id, created_at) FROM stdin;
2	2	1	2026-01-04 20:21:30.144668+03
3	2	2	2026-01-04 20:21:30.144668+03
4	2	3	2026-01-04 20:21:30.144668+03
\.


--
-- Name: camp_admin_accounts_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.camp_admin_accounts_id_seq', 2, true);


--
-- Name: user_events_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.user_events_id_seq', 56, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.users_id_seq', 8, true);


--
-- Name: camp_photos_id_seq; Type: SEQUENCE SET; Schema: catalog; Owner: -
--

SELECT pg_catalog.setval('catalog.camp_photos_id_seq', 175, true);


--
-- Name: camps_id_seq; Type: SEQUENCE SET; Schema: catalog; Owner: -
--

SELECT pg_catalog.setval('catalog.camps_id_seq', 3, true);


--
-- Name: room_photos_id_seq; Type: SEQUENCE SET; Schema: catalog; Owner: -
--

SELECT pg_catalog.setval('catalog.room_photos_id_seq', 280, true);


--
-- Name: rooms_id_seq; Type: SEQUENCE SET; Schema: catalog; Owner: -
--

SELECT pg_catalog.setval('catalog.rooms_id_seq', 123, true);


--
-- Name: admins_id_seq; Type: SEQUENCE SET; Schema: crm; Owner: -
--

SELECT pg_catalog.setval('crm.admins_id_seq', 1, false);


--
-- Name: bookings_id_seq; Type: SEQUENCE SET; Schema: crm; Owner: -
--

SELECT pg_catalog.setval('crm.bookings_id_seq', 7, true);


--
-- Name: camp_admin_links_id_seq; Type: SEQUENCE SET; Schema: crm; Owner: -
--

SELECT pg_catalog.setval('crm.camp_admin_links_id_seq', 4, true);


--
-- Name: camp_admin_accounts camp_admin_accounts_email_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.camp_admin_accounts
    ADD CONSTRAINT camp_admin_accounts_email_key UNIQUE (email);


--
-- Name: camp_admin_accounts camp_admin_accounts_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.camp_admin_accounts
    ADD CONSTRAINT camp_admin_accounts_pkey PRIMARY KEY (id);


--
-- Name: user_events user_events_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_events
    ADD CONSTRAINT user_events_pkey PRIMARY KEY (id);


--
-- Name: user_tokens user_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_tokens
    ADD CONSTRAINT user_tokens_pkey PRIMARY KEY (token);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: camp_photos camp_photos_pkey; Type: CONSTRAINT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.camp_photos
    ADD CONSTRAINT camp_photos_pkey PRIMARY KEY (id);


--
-- Name: camps camps_pkey; Type: CONSTRAINT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.camps
    ADD CONSTRAINT camps_pkey PRIMARY KEY (id);


--
-- Name: room_photos room_photos_pkey; Type: CONSTRAINT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.room_photos
    ADD CONSTRAINT room_photos_pkey PRIMARY KEY (id);


--
-- Name: rooms rooms_pkey; Type: CONSTRAINT; Schema: catalog; Owner: -
--

ALTER TABLE ONLY catalog.rooms
    ADD CONSTRAINT rooms_pkey PRIMARY KEY (id);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (id);


--
-- Name: bookings bookings_pkey; Type: CONSTRAINT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.bookings
    ADD CONSTRAINT bookings_pkey PRIMARY KEY (id);


--
-- Name: camp_admin_links camp_admin_links_pkey; Type: CONSTRAINT; Schema: crm; Owner: -
--

ALTER TABLE ONLY crm.camp_admin_links
    ADD CONSTRAINT camp_admin_links_pkey PRIMARY KEY (id);


--
-- Name: idx_user_events_user_created; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_user_events_user_created ON auth.user_events USING btree (user_id, created_at DESC);


--
-- Name: idx_user_tokens_user_created; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_user_tokens_user_created ON auth.user_tokens USING btree (user_id, created_at DESC);


--
-- Name: idx_users_email_unique; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX idx_users_email_unique ON auth.users USING btree (lower(email)) WHERE ((email IS NOT NULL) AND (email <> ''::text));


--
-- Name: idx_users_phone_unique; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX idx_users_phone_unique ON auth.users USING btree (phone) WHERE ((phone IS NOT NULL) AND (phone <> ''::text));


--
-- PostgreSQL database dump complete
--

\unrestrict lANdggfEm7uFYc62JtmdmoscmOXWW2KYFuElTvwLEe4ZhR7jyczWaOzvfqiR1uN
