# oracledb.exceptions.DatabaseError: ORA-02396: a maximális üresjárati idő túllépve, jelentkezzen be újra
# f.db.close
import string
import traceback

import sqlalchemy
import sqlglot
from sqlalchemy.engine import create_engine
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, ResourceClosedError
from sqlglot.dialects import Oracle
#import oracledb
import unittest

import string

from pathlib import Path
import os

import sys

import random

from typing import *

import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)

import sqlparse

from collections import Counter, namedtuple  # TODO orderedcounter?

import importlib.util as iu

here = Path(__file__).parent


#TODO can have all kinds of issues, needs timeout and reset etc
#TODO fix failed transaction handling
class DB:
    def __init__(self):
        self.eng: sqlalchemy.Engine = None
        self.prefixes = None
        self.conn = None

    #TODO fix nls parameters
    def connect(self, user: str, passw: str): #TODO need to deal with the limits and stuff
        e = create_engine(f"oracle+oracledb://{user}:{passw}@codd.inf.unideb.hu:1521/?service_name=ora21cp.inf.unideb.hu")
        self.eng = e
        self.conn = e.connect()

    def close(self):
        self.conn.close()

    # query
    def q(self, q: str) -> List:  # TODO or raw cursorresult?
        return list(self.conn.execute(text(q)))

    def clean(self):
        pass

Scope = namedtuple("Scope", ["public_synonyms"])

# incorporate name resolution of 2-144 in https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/sql-language-reference.pdf more explicitly
class SQLTransformer:
    """
    >> list(t.parse("SELECT * FROM asd;", 'oracle'))
    [(SELECT expressions:
      (STAR ), from:
      (FROM expressions:
        (TABLE this:
          (IDENTIFIER this: unique_prefix1_asd, quoted: False))))]
    """
    def __init__(self, scope, appprefix, scopeprefix, namespaced_schema, dialect="oracle"):
        self.appprefix = appprefix
        self.scopeprefix = scopeprefix
        self.namespaced_schema = namespaced_schema
        self.dialect = dialect
        self.scope = scope #TODO not dynamic enough? but it will work for now

    #TODO you really shouldnt overcomplicate this like this
    @classmethod
    def compose(cls, transformer, transform2):
        class ComposedTransformer(cls):
            def __init__(self, parent):
                self.parent = parent

            def __getattr__(self, item):
                attr = getattr(self.parent, item)
                if callable(attr):
                    return getattr(self, item)
                else:
                    return attr

            def transform(self, node, transform=None):
                node = self.parent.transform(node, transform)
                return self.parent.transform(node, transform2)

        return ComposedTransformer(transformer)

    def getPrefix(self):
        return self.appprefix + "_" + self.scopeprefix + "_"

    def transform_tablename(self, name):
        return self.getPrefix() + name

    def transform_tablename_scoped(self, scope, name):
        if name.lower() not in scope.public_synonyms:
            return self.transform_tablename(name)
        else:
            return name

    def _static_datetime(self, e):
        if isinstance(e, sqlglot.exp.Identifier):
            if e.this.lower() in ["sysdate"]:
                #e.args["this"] = "TIMESTAMP '2023-03-28 08:00:00'" #TODO hack
                e.args["this"] = "DATE '2023-03-28'" #TODO hack
        return e


    # TODO need to make sure we are only transforming stuff accessing our own schema/user
    # This means we should also track state like current_schema?

    #TODO s***: need to do some sort of scope analysis because of aliases
    #TODO if name is /collides with a synonym, need to figure out if we resolve our own thing or the synonym
    #TODO dont double-apply (make sure transformations are disjoint?)
    #NOTE also does constraints now
    def _prefix_tables(self, e):  # Ok but why
        scope = self.scope #TODO not dynamic enough? but it will work for now
        if isinstance(e, sqlglot.exp.Table):
            # (TABLE this:
            #    (IDENTIFIER this: pls, quoted: False)))
            if e.args["db"] is not None:  # if not our schema/user, dont need to simulate the namespacing
                if e.db != self.namespaced_schema:
                    return e
            #Identifier; (IDENTIFIER this: whatever, quoted: False))
            e.this.args["this"] = self.transform_tablename_scoped(scope, e.this.this)
        elif isinstance(e, sqlglot.exp.Column) and "table" in e.args:
            # (COLUMN this:
            #   (STAR), table:
            #   (IDENTIFIER this: whatever, quoted: False))
            # Identifier; (IDENTIFIER this: whatever, quoted: False))
            #Doing this with bfs from the root should result in the most local scope overriding collisions?
            aliasmap = {x.parent.alias:x.parent.this.this for x in e.root().find_all(sqlglot.exp.TableAlias, bfs=True)}
            tablename = e.args["table"].this
            #TODO memoize this or something
            if tablename not in aliasmap:
                e.args["table"].args["this"] = self.transform_tablename_scoped(scope, tablename) #TODO why is this inconsistent with Table
        elif isinstance(e, sqlglot.exp.Command) and e.this.upper() == "ALTER":  #we need to fall back to sqlparse?
            # ALTER TABLE schema.tablename ...
            #TODO assert single statement
            parsed = sqlparse.parse(e.sql(self.dialect))[0]
            #if in known tables, replace, no other way to know whether a name is a table without knowing syntax?
            # does not handle deferred constraints case but i dont think it needs to?
            #TODO this is not sufficient
            loc = str(parsed).upper().find("ALTER TABLE ")
            assert loc != -1
            identifier_parts = list(x for x in
                                    parsed.get_token_at_offset(loc+len("ALTER TABLE ")).parent.tokens
                                    if x.ttype != sqlparse.tokens.Whitespace)
            assert len(identifier_parts) <= 3
            if len(identifier_parts) == 3 and identifier_parts[0] != self.namespaced_schema:
                return e #TODO test
            identifier_parts[-1].value = self.transform_tablename_scoped(scope, identifier_parts[-1].value)
            if "drop" in str(parsed):
                globals()["xxx"] = parsed
            unparsed = str(parsed)
            e = sqlglot.parse(unparsed, self.dialect)[0]
        elif isinstance(e, sqlglot.exp.ForeignKey):
            # Identifier corresponding to referenced table
            #TODO schema case not handled, parser doesnt handle it either
            e.args["reference"].this.args["this"] = self.transform_tablename_scoped(scope, e.args["reference"].this.this)
        elif isinstance(e, sqlglot.exp.Reference) and not isinstance(e.parent, sqlglot.exp.ForeignKey): #redundant with above for that case
            e.this.args["this"] = self.transform_tablename_scoped(scope, e.this.this)
        elif isinstance(e, sqlglot.exp.Constraint): #TODO handle other constraint names?
            #TODO assert identifier
            e.this.args["this"] = self.transform_tablename_scoped(scope, e.this.this)
        elif isinstance(e, sqlglot.exp.ColumnConstraint): #TODO handle other constraint names?
            #TODO assert identifier
            if e.args["this"] is not None and isinstance(e.this, sqlglot.exp.Identifier):
                e.this.args["this"] = self.transform_tablename_scoped(scope, e.this.this)
        return e

    def _unprefix_tables(self, e):  # Ok but why
        #TODO
        pass

    def transform(self, node, transform=None):
        if node is None:
            return None
        if transform is None:
            transform = self._prefix_tables
        return node.transform(transform)

    def parse(self, *args, **kwargs):
        return map(self.transform, sqlglot.parse(*args, **kwargs))

    def list_tables(self):
        pass

#TODO check against created structure instead of explicit checks
#TODO skip all this and just use the sqlalchemy stuff directly in the checks
#TODO
#TODO need to deal with renaming
class Checker:
    def __init__(self):
        self.db = None
        self.prefix = None #TODO
        self.metadata = None

    def setConn(self, conn, prefix):
        self.conn = conn
        self.prefix = prefix #TODO
        self.m = sqlalchemy.MetaData()
        conn._allow_autobegin = False
        self.m.reflect(bind=self.conn)
        conn._allow_autobegin = True

    def check_state(self):
        raise NotImplementedError

    @classmethod
    def load(cls, path):
        name = path.name
        path = str(path)
        spec = iu.spec_from_file_location(name, path)
        mod = iu.module_from_spec(spec)
        setattr(mod, cls.__name__, cls)
        spec.loader.exec_module(mod)
        return mod.Check() #TODO i might need to mess with the instancing on this because the prefix will need to change across invocations?

    def table_exists(self, tablename):
        # #TODO prepared statements for all of these
        # return len(self.db.conn.execute(text(f"SELECT table_name FROM user_tables WHERE table_name = '{tablename}'"))
        #            .fetchall()) == 1
        #TODO should be using tranform tablename
        tablename = (self.prefix + tablename).lower()
        res = tablename in self.m.tables.keys()
        if not res:
            logging.info(f"column check failed1 {tablename}, {self.m.tables.keys()}")
        return res

    def table_column(self, tablename, columnname, targettype, constrainttype=None, constraints=None):
        tablename = (self.prefix + tablename).lower()
        columnname = columnname.lower()
        if not tablename in self.m.tables:
            logging.info("column check failed2")
            return False
        if not columnname in self.m.tables[tablename].columns.keys():
            logging.info("column check failed3")
            return False
        #TODO will this work generally?
        if not (storedtype:= repr(self.m.tables[tablename].columns[columnname].type)) == \
               (targettype := repr(eval(f"sqlalchemy.dialects.oracle.{targettype}"))): # TODO
            logging.info(f"column check failed4 {tablename}, {columnname}, {repr(targettype)}, {repr(storedtype)}")
            return False
        #TODO
        if constrainttype == "R": # TODO can there be more than one constraint entry per col? this is a set.
            #if not columnname in {c for c in self.m.tables[tablename].constraints if }
            pass
        elif constrainttype == "C":
            pass
        elif constrainttype == "P":
            pass
        elif constrainttype == "U":
            pass
        elif constrainttype is None:
            pass
        else:
            raise NotImplementedError

        # cols = self.db.conn.excute(text(f"select * from user_tab_columns where lower(table_name) = '{tablename}' and lower(column_name) = lower('{columnname}');")).fetchall()
        # if len(cols) != 1:
        #     return False
        # col = cols[0]._mapping
        # #TODO proper datatype handling and an enum, or maybe I can already do this with sqlalchemy or something?
        return True


    def primary_key(self, tablename, columnnames):
        tablename = (self.prefix + tablename).lower()
        columnnames = tuple(x.lower() for x in columnnames)
        if set(columnnames) != (storedcols := set(x.name for x in self.m.tables[tablename].primary_key.columns)):
            logging.info(f"pkey check failed {tablename}, {columnnames}, {storedcols}")
            return False
        return True

    def unique_key(self, tablename, columnnames):
        tablename = (self.prefix + tablename).lower()
        columnnames = tuple(x.lower() for x in columnnames)
        #TODO these are technically indexes not constraints
        if set(columnnames) not in ({y.name for y in x.columns} for x in self.m.tables[tablename].indexes):
            logging.info("ukey check failed")
            return False
        return True

    def foreign_key(self, tablename, referredtable, columnnames):
        tablename = (self.prefix + tablename).lower()
        columnnames = tuple(x.lower() for x in columnnames)
        if {(referredtable, z) for z in columnnames} not in \
                ({(x.referred_table, y.name) for y in x} for x in self.m.tables[tablename].foreign_key_constraints):
            logging.info("fkey check failed")
            return False
        return True

    def check_constraint(self, tablename, constrainttext): #TODO not very flexible
        tablename = (self.prefix + tablename).lower()
        for x in (stored := [y for y in self.m.tables[tablename].constraints if isinstance(y, sqlalchemy.sql.schema.CheckConstraint)]):
            if constrainttext == x.sqltext.text:
                return True
        logging.info(f"cc check failed {tablename}, {constrainttext}, {[x.sqltext.text for x in stored]}")
        return False


class StoredSolution:
    def __init__(self, root_path, specifier, dialect="oracle"):
        self.root_path = root_path
        self.dialect = dialect
        # TODO break out to new function/class
        problemtext, options, solns = open(self.root_path / "problems" / f"{specifier}", "r")\
            .read().split("============")
        self.text = problemtext
        self.options = dict((x[0], eval(x[1])) for l in options.strip().split("\n") for x in [l.split("=")])  # TODO meh eval
        self.sql = solns.split("------------")
        self.checker = None
        if os.path.isfile(checkerpath := (self.root_path / "problems" / f"{specifier}.py")):
            self.checker = Checker.load(checkerpath)

    #TODO assert all solutions are consistent
    def get_stored_solution(self, conn, transformer, mylog):
        #TODO this wont work properly with stuff containing DCL or multistatement
        results = list()
        conn.begin()
        shouldcheckstate = False
        for s in (x for x in transformer.parse(self.sql[0], self.dialect) if x is not None): # TODO only looks at first solution
            if s.__class__.__name__ != "Select":
                shouldcheckstate = True
            statement = text(s.sql(self.dialect))
            try:
                mylog += f"running: {statement}\n"
                r = conn.execute(statement)
                results.append(res := r.fetchall())
                try:  # TODO figure out how to check ahead of time?
                    mylog += "\n".join(",".join(str(cell) for cell in row) for row in res)
                except ResourceClosedError:
                    pass
            except Exception as e:
                traceback.print_exc()
                strs = traceback.format_exc()
                mylog += "".join(strs)
        conn.rollback()
        if shouldcheckstate:
            state = sqlalchemy.MetaData()#TODO probably not how this should work
            conn._allow_autobegin = False
            state.reflect(bind=conn)
            conn._allow_autobegin = True
        else:
            state = None
        return results, state, shouldcheckstate

    def get_my_solution(self, sqltext, conn, transformer, shouldcheckstate, mylog):
        #TODO this wont work properly with stuff containing DCL or multistatement
        results = list()
        conn.begin()
        for s in (x for x in transformer.parse(sqltext, self.dialect) if x is not None):
            statement = text(s.sql(self.dialect))
            try:
                mylog += f"running: {statement}\n"
                r = conn.execute(statement)
                results.append(res := r.fetchall())
                try:
                    mylog += "\n".join(",".join(str(cell) for cell in row) for row in res)
                except ResourceClosedError:  # TODO figure out how to check ahead of time?
                    pass
            except ResourceClosedError:
                traceback.print_exc()
                strs = traceback.format_exc()
                mylog += "".join(strs)
        conn.rollback()
        if shouldcheckstate:
            state = sqlalchemy.MetaData()#TODO probably not how this should work
            conn._allow_autobegin = False
            state.reflect(bind=conn)
            conn._allow_autobegin = True
        else:
            state = None
        return results, state

    #TODO improve flexibility; column permutations, superset of columns, ...?
    #TODO add diffing
    #TODO difftable type
    # note columns are permutable semantically but not wrt code; returned tuples are ordered (thoguh its possible to get col list?)
    # without deep sql semantic analysis (or talking to the server?/EXPLAIN) i dont think its possible to figure out if columns are the same / from the same data
    # TODO doesnt handle multiple statements, doesnt handle empty results (the one comment problem)
    def compare_lists_of_resultbags(self, r1, r2, order_matters):
        for a, b in zip(r1, r2):
            return Counter(a) == Counter(b)
        if len(r1) == 0 and len(r2) == 0:
            return True
        else:
            return False

    #TODO its redundant passing both reflection objects because they both contain the rest of the database info anyway
    def compare_state(self, storedtransformer, mytransformer, storedmetadata, mymetadata, **kwargs):
        #TODO could just match whitelisted / blacklisted columns of data dictionary?
        for t in [_t for _t in storedmetadata.tables if _t.startswith(storedtransformer.getPrefix())]:
            storedcolumnnames = [_c.name for _c in storedmetadata.tables[t].columns]
            try:
                equivtable = mytransformer.getPrefix() + t.replace(storedtransformer.getPrefix(), "")
                mycolumns = [_c.name for _c in mymetadata.tables[equivtable].columns]
            except Exception as e:
                raise e
            #mycolnames = [x.name for x in mycolumns]
            for cname in storedcolumnnames:
                if not cname in mycolumns:
                    logging.info(f"{cname} in ({storedtransformer.getPrefix()},{t}) missing from  ({mytransformer.getPrefix()},{t})")
                    return False
                else:
                    pass #TODO constraints
            for co in [_co for _co in storedmetadata.tables[t].constraints]:
                pass #TODO constraints
        return True # TODO more descriptive

    #TODO something about limiting fetched row count to not DOS yourself
    def check_solution(self, sqltext, conn, _transformer, feladatsor, mylog, reuse_stored=None, reuse_my=None):
        # TODO deal with collisions, this shouldnt be random
        # TODO this shouldnt work, why does it work
        my_randomprefix = "".join(random.choices(string.ascii_lowercase, k=6)) if reuse_my is None else reuse_my
        stored_randomprefix = "".join(random.choices(string.ascii_lowercase, k=6)) if reuse_stored is None else reuse_stored
        my_transformer = SQLTransformer(_transformer.scope, _transformer.appprefix, my_randomprefix,
                                        _transformer.namespaced_schema, _transformer.dialect)
        stored_transformer = SQLTransformer(_transformer.scope, _transformer.appprefix, stored_randomprefix,
                                            _transformer.namespaced_schema, _transformer.dialect)
        #TODO doesnt handle multiple statements, doesnt handle empty results (the one comment problem)
        my_transformer = SQLTransformer.compose(my_transformer, my_transformer._static_datetime)
        stored_transformer = SQLTransformer.compose(stored_transformer, stored_transformer._static_datetime)
        if sqltext == None:
            sqltext = self.sql[0]#TODO

        #TODO for each permutation check equal subsets, ignore empties?
        try:
            if reuse_stored is None:
                feladatsor.init_env(stored_transformer)
            if reuse_my is None:
                feladatsor.init_env(my_transformer)
            storedresult, storedstate, checkstate = self.get_stored_solution(conn, stored_transformer, mylog)
            myresult, mystate = self.get_my_solution(sqltext, conn, my_transformer, checkstate, mylog)
        except Exception: #TODO #NOTE: parseerror, databaseerror, ...?
            traceback.print_exc()
            conn.rollback() #TODO this doesnt realy do what it's supposed to here, this is just so sqlalchemy doesnt complain about transaction state
            return my_transformer, stored_transformer, False
        if checkstate:
            if self.checker:
                # TODO structure
                #TODO this wont work properly with stuff containing DCL or multistatement
                self.checker.setConn(conn, my_transformer.getPrefix()) #TODO instancing
                checkstate = self.checker.check_state()
            else:
                checkstate = self.compare_state(my_transformer, stored_transformer, mystate, storedstate, **self.options)
            if not checkstate or checkstate is None: #TODO assert checkstate not none?
                return my_transformer, stored_transformer, False
        return my_transformer, stored_transformer, self.compare_lists_of_resultbags(myresult, storedresult, **self.options)


#TODO need to introduce dependencies between problems and in their checking
class Feladatsor(): #TODO rename to feladat, differentiate feladatsor and feladat objects?
    def __init__(self, db: DB, transformer: SQLTransformer, name: str, files: Dict[str, str], dialect='oracle'):
        self.db = db
        self.name = name
        self.files = files
        self.transformer = transformer
        self.root_path = here / "sql_envs" / name
        self.dialect = dialect

    def _prep_sql(self, fileset, transformer):
        statements = list()
        for fname in self.files[fileset]:
            raw_sql = open(self.root_path / "scripts" / fname, "r").read() #TODO
            ##TODO UNSAFE!, but sqlglot is slow on large files
            #unparsed_statements = raw_sql.split(";")
            #for s in unparsed_statements: #TODO lone comments currently cause an error and need to be filtered
            #    statements.extend(self.transformer.parse(s, self.dialect))
            statements.extend(transformer.parse(raw_sql, self.dialect))
        return (x for x in statements if x is not None)

    #TODO bleh oracle commits after every DDL statement so the transactional stuff here is kind of pointless

    #TODO use/load stored procs to make these faster?
    # todo sqlalchemy.exc.DatabaseError: (oracledb.exceptions.DatabaseError) ORA-00955: name is already used by an existing object
    def init_env(self, transformer):
        #todo with transaction or something
        for c in ("create", "insert", "init"): #TODO need to cache insert set, or maybe split it?, sqlglot is not fast for a file this large.
            logging.info(f"Executing {c} set.")
            statements = self._prep_sql(c, transformer)
            with self.db.conn.begin(): #TODO factor
                for s in statements: #TODO didnt roll back on exception / closing connection?
                    self.db.conn.execute(text(s.sql(self.dialect)))

    def del_env(self, transformer):
        statements = self._prep_sql("delete", transformer)
        logging.info("Executing delete set.")
        logging.info("DELETE SET PATCHED OUT FOR NOW")
        self.del_all_env(transformer) #TODO less shotgun
        return

        with self.db.conn.begin(): #TODO needs a lock
            for s in statements:
                try:
                    self.db.conn.execute(text(s.sql(self.dialect)))
                except DatabaseError as e:
                    if not "table or view does not exist" in e._message(): #TODO #TODO ora code
                        raise e

    def del_all_env(self, transformer):
        #TODO use prepared statement instead
        prefix = transformer.appprefix.replace("/", "//").replace("_", "/_").replace("%", "/%")
        # #TODO oh god this is such a hack surely there is a better way to do this
        # self.db.conn._allow_autobegin = False
        # self.db.conn.execute(text(f"""
        # BEGIN
        #     FOR t IN (SELECT table_name FROM user_tables WHERE LOWER(table_name) LIKE '{prefix}%' ESCAPE '/')
        #     LOOP
        #         EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE;';
        #     END LOOP;
        # END;
        # """))
        # self.db.conn._allow_autobegin = True
        tables = self.db.conn.execute(text(f"SELECT table_name FROM user_tables WHERE LOWER(table_name) LIKE '{prefix}%' ESCAPE '/'")).fetchall()
        for t in tables:
            self.db.conn.execute(text(f"DROP TABLE {t[0]} CASCADE CONSTRAINTS PURGE"))
        self.db.conn.commit()

    def reset_env(self, transformer):
        self.del_env(transformer)
        self.init_env(transformer)

    def check_solution(self, fname, sqltext, mylog, reuse_my=None, reuse_stored=None):
        soln = StoredSolution(self.root_path, fname)
        return soln.check_solution(sqltext, self.db.conn, self.transformer, self, mylog, reuse_my, reuse_stored)

class Session:
    def __init__(self, user, passw):
        self.prefix = "unique_prefix1_"
        self.d = DB()
        self.d.connect(user, passw)
        #TODO un****
        self.d.conn.execute(text("alter session set NLS_NUMERIC_CHARACTERS=',.'"))
        self.synonyms = [x[0].lower() for x in self.d.conn.execute(text("select synonym_name from all_synonyms")).fetchall()]
        self.d.conn.commit() # needed because above implicitly starts transaction...
        self.scope = Scope(public_synonyms=self.synonyms)  # TODO not dynamic enough? but it will work for now
        self.t = SQLTransformer(self.scope, "sqltrainer", self.prefix, user)

        self.f = Feladatsor(self.d, self.t, "konyvtar", {"create": ["konyvtar_create.sql"],  # TODO assert all exist (construct path object)
                                      "insert": ["konyvtar_insert.sql"],
                                      "init": [],  # TODO cant handle pl/sql ["update_date_ship.sql"], # TODO handle None or missing
                                      "delete": ["konyvtar_delete.sql"]})
        self.f.reset_env(self.f.transformer)


class Test(unittest.TestCase):
    def testkonyvtar(self):
        prefix = "unique_prefix1_"
        d = DB()
        d.connect(*open("cred","r").read().split(":"))
        #TODO un****
        d.conn.execute(text("alter session set NLS_NUMERIC_CHARACTERS=',.'"))
        synonyms = [x[0].lower() for x in d.conn.execute(text("select synonym_name from all_synonyms")).fetchall()]
        d.conn.commit() # needed because above implicitly starts transaction...
        scope = Scope(public_synonyms=synonyms)  # TODO not dynamic enough? but it will work for now
        t = SQLTransformer(scope, "sqltrainer", prefix, open("cred","r").read().split(":")[0])
        f = Feladatsor(d, t, "konyvtar", {"create": ["konyvtar_create.sql"],  # TODO assert all exist (construct path object)
                                      "insert": ["konyvtar_insert.sql"],
                                      "init": [],  # TODO cant handle pl/sql ["update_date_ship.sql"], # TODO handle None or missing
                                      "delete": ["konyvtar_delete.sql"]})
        f.reset_env(f.transformer)
        # assert f.check_solution(1, "select *  from tag ORDER BY vezeteknev DESC") == True
        # # TODO cant be true because db insertion has randomized data
        # #assert f.check_solution(1, "select *  from konyvtar.tag ORDER BY vezeteknev DESC") == True
        # assert f.check_solution(1, "select 1 from dual") == False
        #TODO tests that use sysdate will fail erratically! TODO to work around this we insert a static date value in the transformer
        my_transformer, stored_transformer = None, None
        mylog = ""
        for fname in os.listdir(f.root_path / "problems"):
            # if fname != "f_173":
            #     continue
            if not os.path.isfile(f.root_path / "problems" / fname) or fname.endswith(".py"):
                continue
            print(fname)
            #TODO pure environments, i.e. reset, and  also, make init faster
            with self.subTest(fname): #TODO how to get pycharm to log subtests properly?
                #assert f.check_solution("f_1", "select *  from konyvtar.tag ORDER BY vezeteknev DESC") == True
                my_transformer, stored_transformer, result = f.check_solution(fname, None, mylog,
                                                                              reuse_stored=stored_transformer.scopeprefix if stored_transformer is not None else None,
                                                                              reuse_my=my_transformer.scopeprefix if my_transformer is not None else None)
                self.assertTrue(result)
                _, _, result = f.check_solution(fname, "select 65537 from dual", mylog, reuse_stored=stored_transformer.scopeprefix, reuse_my=my_transformer.scopeprefix)
                self.assertFalse(result)

    @unittest.skip
    def testhajo(self):
        prefix = "unique_prefix1_"
        d = DB()
        d.connect(*open("cred","r").read().split(":"))
        #TODO un****
        d.conn.execute(text("alter session set NLS_NUMERIC_CHARACTERS=',.'"))
        d.conn.execute(text("select * from all_synonyms"))
        d.conn.commit() # needed because above implicitly starts transaction...
        synonyms = [x[0].lower() for x in d.conn.execute(text("select synonym_name from all_synonyms")).fetchall()]
        scope = Scope(public_synonyms=synonyms)  # TODO not dynamic enough? but it will work for now
        t = SQLTransformer(scope, prefix, open("cred","r").read().split(":")[0])
        f = Feladatsor(d, t, "hajo", {"create": ["create_ship.sql"],  # TODO assert all exist (construct path object)
                                      "insert": ["insert_ship.sql"],
                                      "init": [],  # TODO cant handle pl/sql ["update_date_ship.sql"],
                                      "delete": ["delete_ship.sql"]})
        f.reset_env(f.transformer)
        for fname in os.listdir(f.root_path / "problems"):
            #assert f.check_solution("f_1", "select *  from konyvtar.tag ORDER BY vezeteknev DESC") == True
            assert f.check_solution("f_1", None) == True
            assert f.check_solution("f_1", "select 65537 from dual") == False


if __name__ == '__main__':
    prefix = "unique_prefix1_"
    d = DB()
    d.connect(*open("cred","r").read().split(":"))
    synonyms = [x[0].lower() for x in d.conn.execute(text("select synonym_name from all_synonyms")).fetchall()]
    scope = Scope(public_synonyms=synonyms)# TODO not dynamic enough? but it will work for now
    t = SQLTransformer(scope, prefix, open("cred","r").read().split(":")[0])
    f = Feladatsor(d, t, "hajo", {"create": ["create_ship.sql"], #TODO assert all exist (construct path object)
                                  "insert": ["insert_ship.sql"],
                                  "init": [], #TODO cant handle pl/sql ["update_date_ship.sql"],
                                  "delete": ["delete_ship.sql"]})
    print()