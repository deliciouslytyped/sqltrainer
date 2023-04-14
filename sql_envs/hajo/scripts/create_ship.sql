CREATE TABLE s_hajo (
    hajo_id               VARCHAR2(10) NOT NULL,
    nev                   VARCHAR2(30) NOT NULL,
    netto_suly            NUMBER(10,4),
    max_kontener_dbszam   NUMBER(5),
    max_sulyterheles      NUMBER(10,4),
    hajo_tipus            NUMBER(3)
);

COMMENT ON COLUMN s_hajo.netto_suly IS
    'tonna';

COMMENT ON COLUMN s_hajo.max_sulyterheles IS
    'tonna';

ALTER TABLE s_hajo ADD CONSTRAINT s_hj_pk PRIMARY KEY ( hajo_id );

CREATE TABLE s_hajo_tipus (
    hajo_tipus_id   NUMBER(3) NOT NULL,
    nev             VARCHAR2(30) NOT NULL,
    leiras          VARCHAR2(150)
);

ALTER TABLE s_hajo_tipus ADD CONSTRAINT s_hjt_pk PRIMARY KEY ( hajo_tipus_id );

CREATE TABLE s_helyseg (
    helyseg_id   NUMBER(10) NOT NULL,
    orszag       VARCHAR2(50) NOT NULL,
    helysegnev   VARCHAR2(35) NOT NULL,
    lakossag     NUMBER(8)
);

ALTER TABLE s_helyseg ADD CONSTRAINT s_hs_pk PRIMARY KEY ( helyseg_id );

CREATE TABLE s_hozzarendel (
    megrendeles    VARCHAR2(15) NOT NULL,
    kontener       NUMBER(5) NOT NULL,
    rakomanysuly   NUMBER(6,4)
);

COMMENT ON COLUMN s_hozzarendel.rakomanysuly IS
    'tonna';

ALTER TABLE s_hozzarendel ADD CONSTRAINT s_hr_pk PRIMARY KEY ( megrendeles,kontener );

CREATE TABLE s_kikoto (
    kikoto_id   VARCHAR2(10) NOT NULL,
    helyseg     NUMBER(10) NOT NULL,
    leiras      VARCHAR2(250)
);

ALTER TABLE s_kikoto ADD CONSTRAINT s_kk_pk PRIMARY KEY ( kikoto_id );

CREATE TABLE s_kikoto_telefon (
    kikoto_id   VARCHAR2(10) NOT NULL,
    telefon     VARCHAR2(20) NOT NULL
);

ALTER TABLE s_kikoto_telefon ADD CONSTRAINT s_kkt_pk PRIMARY KEY ( kikoto_id,telefon );

CREATE TABLE s_megrendeles (
    megrendeles_id          VARCHAR2(15) NOT NULL,
    indulasi_kikoto         VARCHAR2(10),
    erkezesi_kikoto         VARCHAR2(10),
    megrendeles_datuma      DATE NOT NULL,
    ugyfel                  NUMBER(10) NOT NULL,
    fizetett_osszeg         NUMBER(20),
    igenyelt_kontenerszam   NUMBER(10)
);

COMMENT ON COLUMN s_megrendeles.fizetett_osszeg IS
    'USA doll�r';

ALTER TABLE s_megrendeles ADD CONSTRAINT s_mr_pk PRIMARY KEY ( megrendeles_id );

ALTER TABLE s_megrendeles ADD CONSTRAINT s_mr_uq UNIQUE ( ugyfel,megrendeles_datuma );

CREATE TABLE s_orszag (
    orszag     VARCHAR2(50) NOT NULL,
    lakossag   NUMBER(10),
    terulet    NUMBER(10),
    foldresz   VARCHAR2(30),
    fovaros    NUMBER(10)
);

COMMENT ON COLUMN s_orszag.terulet IS
    'km2';

ALTER TABLE s_orszag ADD CONSTRAINT s_osz_pk PRIMARY KEY ( orszag );

CREATE TABLE s_szallit (
    ut            VARCHAR2(30) NOT NULL,
    kontener      NUMBER(5) NOT NULL,
    megrendeles   VARCHAR2(15) NOT NULL
);

ALTER TABLE s_szallit
    ADD CONSTRAINT s_sz_pk PRIMARY KEY ( kontener,ut,megrendeles );

CREATE TABLE s_ugyfel (
    ugyfel_id    NUMBER(10) NOT NULL,
    vezeteknev   VARCHAR2(30) NOT NULL,
    keresztnev   VARCHAR2(30) NOT NULL,
    telefon      VARCHAR2(20),
    email        VARCHAR2(30),
    szul_dat     DATE,
    helyseg      NUMBER(10),
    utca_hsz     VARCHAR2(30)
);

ALTER TABLE s_ugyfel
    ADD CONSTRAINT s_uf_et_ck CHECK (
            telefon IS NOT NULL
        OR
            email IS NOT NULL
    );

ALTER TABLE s_ugyfel ADD CONSTRAINT s_uf_pk PRIMARY KEY ( ugyfel_id );

CREATE TABLE s_ut (
    ut_id             VARCHAR2(30) NOT NULL,
    indulasi_ido      DATE,
    erkezesi_ido      DATE,
    indulasi_kikoto   VARCHAR2(10) NOT NULL,
    erkezesi_kikoto   VARCHAR2(10) NOT NULL,
    hajo              VARCHAR2(10) NOT NULL
);

ALTER TABLE s_ut ADD CONSTRAINT s_ut_pk PRIMARY KEY ( ut_id );

ALTER TABLE s_ut ADD CONSTRAINT s_ut_uq UNIQUE ( indulasi_ido,hajo );

ALTER TABLE s_hajo
    ADD CONSTRAINT s_hj_hjt_fk FOREIGN KEY ( hajo_tipus )
        REFERENCES s_hajo_tipus ( hajo_tipus_id );

ALTER TABLE s_hozzarendel
    ADD CONSTRAINT s_hr_mr_fk FOREIGN KEY ( megrendeles )
        REFERENCES s_megrendeles ( megrendeles_id );

ALTER TABLE s_helyseg
    ADD CONSTRAINT s_hs_osz_fk FOREIGN KEY ( orszag )
        REFERENCES s_orszag ( orszag );

ALTER TABLE s_kikoto
    ADD CONSTRAINT s_kk_hs_fk FOREIGN KEY ( helyseg )
        REFERENCES s_helyseg ( helyseg_id );

ALTER TABLE s_kikoto_telefon
    ADD CONSTRAINT s_kkt_kk_fk FOREIGN KEY ( kikoto_id )
        REFERENCES s_kikoto ( kikoto_id );

ALTER TABLE s_megrendeles
    ADD CONSTRAINT s_mr_ekk_fk FOREIGN KEY ( erkezesi_kikoto )
        REFERENCES s_kikoto ( kikoto_id );

ALTER TABLE s_megrendeles
    ADD CONSTRAINT s_mr_ikk_fk FOREIGN KEY ( indulasi_kikoto )
        REFERENCES s_kikoto ( kikoto_id );

ALTER TABLE s_megrendeles
    ADD CONSTRAINT s_mr_uf_fk FOREIGN KEY ( ugyfel )
        REFERENCES s_ugyfel ( ugyfel_id );

ALTER TABLE s_orszag
    ADD CONSTRAINT s_osz_hs_fk FOREIGN KEY ( fovaros )
        REFERENCES s_helyseg ( helyseg_id );

ALTER TABLE s_szallit
    ADD CONSTRAINT s_sz_hr_fk FOREIGN KEY ( megrendeles,kontener )
        REFERENCES s_hozzarendel ( megrendeles,kontener );

ALTER TABLE s_szallit
    ADD CONSTRAINT s_sz_ut_fk FOREIGN KEY ( ut )
        REFERENCES s_ut ( ut_id );

ALTER TABLE s_ugyfel
    ADD CONSTRAINT s_uf_hs_fk FOREIGN KEY ( helyseg )
        REFERENCES s_helyseg ( helyseg_id );

ALTER TABLE s_ut
    ADD CONSTRAINT s_ut_ekk_fk FOREIGN KEY ( erkezesi_kikoto )
        REFERENCES s_kikoto ( kikoto_id );

ALTER TABLE s_ut
    ADD CONSTRAINT s_ut_hj_fk FOREIGN KEY ( hajo )
        REFERENCES s_hajo ( hajo_id );

ALTER TABLE s_ut
    ADD CONSTRAINT s_ut_ikk_fk FOREIGN KEY ( indulasi_kikoto )
        REFERENCES s_kikoto ( kikoto_id );

