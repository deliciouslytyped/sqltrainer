CREATE TABLE szerzo (
  szerzo_azon		NUMBER(10)		CONSTRAINT szerzo_pk PRIMARY KEY
, vezeteknev		VARCHAR2(30)
, keresztnev		VARCHAR2(20)
, szuletesi_datum	DATE
);

CREATE TABLE konyv (
  konyv_azon		NUMBER(10)		CONSTRAINT konyv_pk PRIMARY KEY
, cim				VARCHAR2(200)	CONSTRAINT konyv_cim_nn NOT NULL
, isbn              VARCHAR2(13)	CONSTRAINT konyv_isbn_uq UNIQUE
, kiado             VARCHAR2(200)
, kiadas_datuma		DATE
, ar				NUMBER(8)
, tema				VARCHAR2(30)
, oldalszam			NUMBER(4)
);

CREATE TABLE konyvszerzo (
  szerzo_azon		NUMBER(10)		CONSTRAINT konyvszerzo_szerzo_fk REFERENCES szerzo
, konyv_azon		NUMBER(10)		CONSTRAINT konyvszerzo_konyv_fk REFERENCES konyv
, honorarium		NUMBER
, CONSTRAINT konyvszerzo_pk PRIMARY KEY (szerzo_azon, konyv_azon)
);

CREATE TABLE tag (
  olvasojegyszam	VARCHAR2(20)	CONSTRAINT tag_pk PRIMARY KEY
, vezeteknev		VARCHAR2(30)
, keresztnev		VARCHAR2(20)
, szuletesi_datum	DATE
, nem				CHAR(1)
, cim				VARCHAR2(200)
, beiratkozasi_datum DATE
, tagdij			NUMBER(5)
, besorolas			VARCHAR2(20)
);

CREATE TABLE konyvtari_konyv (
  leltari_szam		VARCHAR2(20)	CONSTRAINT konyvtari_konyv_pk PRIMARY KEY
, konyv_azon		NUMBER(10)		CONSTRAINT konyvtari_konyv_konyv_azon_fk REFERENCES konyv CONSTRAINT konyvtari_konyv_konyv_azon_nn NOT NULL
, ertek				NUMBER(10,2)
);

CREATE TABLE kolcsonzes (
  tag_azon			VARCHAR2(20)	CONSTRAINT kolcsonzes_tag_azon_fk REFERENCES tag
, leltari_szam		VARCHAR2(20)	CONSTRAINT kolcsonzes_leltari_szam_fk REFERENCES konyvtari_konyv
, kolcsonzesi_datum DATE
, hany_napra		NUMBER(3)		DEFAULT 30
, visszahozasi_datum DATE
, kesedelmi_dij		NUMBER(6)
, CONSTRAINT kolcsonzes_pk PRIMARY KEY (tag_azon, leltari_szam, kolcsonzesi_datum)
);
