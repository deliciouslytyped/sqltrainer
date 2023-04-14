# TODO logging
# TODO frontend
# TODO store oracle session / login in sessioncookie
import traceback

import sqlalchemy
# references
# https://flask.palletsprojects.com/en/2.2.x/
# (https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/)
# https://oracle.github.io/python-oracledb/
# (https://docs.sqlalchemy.org/en/20/dialects/oracle.html)
# https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html
# https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html



from flask import Flask
from flask import render_template
from flask import request
from flask import session
from flask import g
from sqlalchemy.engine import create_engine
from sqlalchemy import text
import re

import sqlite3

import sql_mgr
import sql_envs.konyvtar.gen_problems as gen_problems

import tempfile

import pickle

import sqlglot

# def Frontend:
#     pass
#
# def User:
#     # store user progress; started, correct, nonstarted,
#     # keep history of attempts for each problem
#     pass


app = Flask(__name__)

# cant us in memory database because reasons...th emultithreading multiwhatever is the reason we need to use a db to manage global state
#DATABASE = ':memory:'
DATABASE = tempfile.NamedTemporaryFile(delete=False).name
print(DATABASE)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

with app.app_context():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS sessioncounter(id PRIMARY KEY, counter)")
    cur.execute("CREATE TABLE IF NOT EXISTS savedresults(uid, problem, result, PRIMARY KEY (uid, problem))")
    cur.execute("INSERT INTO sessioncounter VALUES (0,0 )")
    conn.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

#TODO note expiring cookies on problemset changes, at least as long as sessiones are stored client side
app.secret_key = "blahblahblah"

problems = gen_problems.parseall()

@app.route('/', methods=["GET", "POST"])
def page():
    conn = get_db()
    cur = conn.cursor()
    if "sessioncounter" not in g:
        g.sessioncounter = cur.execute("SELECT * FROM sessioncounter").fetchone()[0]

    #TODO autodelete cookie in dev mode?
    #TODO can I defaultdict this?

    problemcount = problems[-1][1][-1][0]
    doSQL = False

    if "problemstate" not in session:
        # 1-based indexing shenaningans
        session["problemstate"] = { "KONYVTAR": [None] + ["unattempted" for i in range(problemcount)]}
        session.modified = True
    if "savedstate" not in session:
        session["savedstate"] = {"KONYVTAR": {**{str(i+1): {"mysolution": "", "show_ans": ""} for i in range(problemcount)}, **{"pinschema": "hide2"}}}
        for k in ["user", "pass", "sessionsql", "tutorial_1"]:
            session["savedstate"][k] = ""
        session.modified = True
    if "i" not in session:
        g.sessioncounter += 1
        session["i"] = g.sessioncounter
        cur.execute("INSERT OR REPLACE INTO sessioncounter (id, counter) VALUES (?, ?)", (0, g.sessioncounter,))
        session.modified = True

    if session: #TODO this is redundant something is broken
        if request.method == "POST":
            for k, v in request.form.items():
                if m := re.fullmatch("KONYVTAR_problem_([0-9]+)_button", k):
                    activeproblem = m[1]
                    doSQL = True
                if m := re.fullmatch("KONYVTAR_problem_([0-9]+)_sql", k):
                    session["savedstate"]["KONYVTAR"][m[1]]["mysolution"] = v
                if m := re.fullmatch("KONYVTAR_([0-9]+)_show_ans", k): #TODO need to handle deletion
                    session["savedstate"]["KONYVTAR"][m[1]]["show_ans"] = "checked"
                if re.fullmatch("pin_schema_KONYVTAR", k):
                    session["savedstate"]["KONYVTAR"]["pinschema"] = v
            session["savedstate"]["pass"] = request.form["pass"]
            session["savedstate"]["user"] = request.form["user"]
            session["savedstate"]["sessionsql"] = request.form["session_sql"]
            session["savedstate"]["tutorial_1"] = request.form["tutorial_1"]
            session.modified = True

    if session and "savedresults" not in g:
        g.savedresults = {k:pickle.loads(v) for k,v in cur.execute("SELECT problem, result FROM savedresults WHERE uid = ?", (int(session["i"]),)).fetchall()}

    if doSQL:
        log = ""
        #TODO ugh i need to implement some whole sessionless state manager crap due to lack of persistent state
        s = sql_mgr.Session(session["savedstate"]["user"], session["savedstate"]["pass"])
        for statement in (x for x in sqlglot.parse(session["savedstate"]["sessionsql"]) if x is not None):
            try:
                log += f"running: {statement}\n"
                s.d.conn.begin()
                res = s.d.conn.execute(text(statement.sql(s.t.dialect)))
                s.d.conn.commit()
                try: #TODO figure out how to check ahead of time?
                    log += "\n".join(",".join(str(cell) for cell in row) for row in res.fetchall())
                except sqlalchemy.exc.ResourceClosedError:
                    pass
            except Exception as e:
                traceback.print_exc(e)
                strs = traceback.format_exception()
                log += "".join(strs)
            finally:
                s.d.conn.commit()

        results = list()
        for statement in (x for x in sqlglot.parse(session["savedstate"]["KONYVTAR"][activeproblem]["mysolution"]) if x is not None):
            try:
                log += f"running: {statement}\n"
                s.d.conn.begin()
                res = s.d.conn.execute(text(statement.sql(s.t.dialect)))
                results.append(res)
                try:  # TODO figure out how to check ahead of time?
                    log += "\n".join(",".join(str(cell) for cell in row) for row in res.fetchall())
                except sqlalchemy.exc.ResourceClosedError:
                    pass
            except Exception as e:
                traceback.print_exc()
                strs = traceback.format_exc()
                log += "".join(strs)
            finally:
                s.d.conn.commit()

        try:
            session["problemstate"]["KONYVTAR"][int(activeproblem)] = "correct" if s.f.check_solution(f"f_{int(activeproblem):03}", session["savedstate"]["KONYVTAR"][activeproblem]["mysolution"]) else "wrong"
        except Exception as e:
            traceback.print_exc()
            strs = traceback.format_exc()
            log += "".join(strs)
            session["problemstate"]["KONYVTAR"][int(activeproblem)] = "wrong"
        finally:
            try:
                s.d.conn.commit()
            except Exception:
                pass

        #TODO due to cookie size limits we cant just store everything in the cookie, so we need to store query results and such on the server somewhere
        g.savedresults[int(activeproblem)] = log
        cur.execute("INSERT OR REPLACE INTO savedresults (uid, problem, result) VALUES (?, ?, ?)", (int(session["i"]), int(activeproblem), pickle.dumps(log)))

    #g.savedresults_maxlen = {k: max(len(",".join(str(x) for x in r)) for r in v) for k,v in g.savedresults.items()}
    g.savedresults_maxlen = {k: max(len(l) for l in v.split()) for k,v in g.savedresults.items()}
    conn.commit()
    return render_template("frontend_en.html", problemsets=[("KONYVTAR", problems)])


if __name__ == '__main__':
    app.run()
