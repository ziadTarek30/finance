import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session["user_id"]
    cash = db.execute("select cash from users where id = ?", id)
    table = db.execute("select * from indext where users_id = ?", id)
    for item in table:
        item["price"] = usd(item["price"])
        item["total"] = usd(item["total"])
    total = db.execute("select sum(total) from indext where users_id = ?", id)
    if '$' not in str(cash[0]["cash"]):
        if total[0]["sum(total)"] == None:
            grandtotal = float(cash[0]["cash"])
        else:
            grandtotal = float(total[0]["sum(total)"]) + float(cash[0]["cash"])
        cashdollar = usd(cash[0]["cash"])
    else:
        cashdollar = cash[0]["cash"]
        cashf = float(cash[0]["cash"][1:].replace(',', ''))
        grandtotal = float(total[0]["sum(total)"]) + cashf

    grandtotaldollar = usd(grandtotal)
    return render_template("infotable.html", table=table, cashdollar=cashdollar, grandtotaldollar=grandtotaldollar)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        id = session["user_id"]
        sharesbought = request.form.get("shares")
        try:
            sb = float(sharesbought)
        except:
            return apology("Numeric charachters are allowed only for shares")
        else:
            if sb <= 0:
                return apology("Only positive numbers are allowed")
            if sb % 1 != 0:
                return apology("Only integers are allowed")
        symbolbought = request.form.get("symbol")
        quote = lookup(symbolbought)
        if not quote:
            return apology("Invalid stock symbol")
        total = float(sharesbought) * float(quote["price"])
        cash = db.execute("select cash from users where id = ?", id)
        if total > float(cash[0]["cash"]):
            return apology("Not enough cash")
        new_cash = float(cash[0]["cash"]) - total
        boughtbefore = db.execute("select symbol from indext where users_id = ? and symbol = ?", id, symbolbought)
        if boughtbefore:
            old_shares = db.execute("select shares from indext where symbol = ? and users_id = ?", symbolbought, id)
            new_shares = old_shares[0]["shares"] + int(sharesbought)
            old_total = db.execute("select total from indext where symbol = ? and users_id = ?", symbolbought, id)
            if '$' in str(old_total[0]["total"]):
                new_total = float(old_total[0]["total"][1:].replace(',', '')) + total
            else:
                new_total = float(old_total[0]["total"]) + total
            db.execute("update indext set shares = ? where symbol = ? and users_id = ?", new_shares, symbolbought, id)
            db.execute("update indext set total = ? where symbol = ? and users_id = ?", new_total, symbolbought, id)
        else:
            db.execute("insert into indext (symbol, name, shares, price, total, users_id) values(?,?,?,?,?,?)", symbolbought, quote["name"], sharesbought, quote["price"], total, id)
        db.execute("update users set cash = ? where id = ?", new_cash, id)
        db.execute("insert into history (symbol, shares, price, h_id) values (?,?,?,?)", symbolbought, sharesbought, quote["price"], id)
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    table = db.execute("select * from history where h_id = ?", session["user_id"])
    for item in table:
        item["price"] = usd(item["price"])
    return render_template("history.html", table=table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        symbols = lookup(symbol)
        if not symbols:
            return apology("Invalid stock symbol", 400)
        symbols["price"] = usd(symbols["price"])
        return render_template("quoted.html", symbols=symbols)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        if not request.form.get("password"):
            return apology("must provide password", 400)
        if not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)
        usernames = db.execute("select username from users where username = ?", request.form.get("username"))
        if usernames:
            return apology("username already taken", 400)
        hash = generate_password_hash(request.form.get("password"))
        db.execute("insert into users (username, hash) values(?,?)", request.form.get("username"), hash)
        id = db.execute("select id from users where username = ?", request.form.get("username"))
        session["user_id"] = id[0]["id"]
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        symbols = db.execute("select symbol from indext where users_id = ?", session["user_id"])
        return render_template("sell.html", symbols=symbols)
    else:
        try:
            sharesnum = float(request.form.get("shares"))
        except:
            return apology("numeric charachters required for shares")
        else:
            if sharesnum <= 0:
                return apology("non positive integer for shares")
            elif sharesnum % 1 != 0:
                return apology("not integer number for shares")
        id = session["user_id"]
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        sharesowned = db.execute("select shares from indext where symbol = ? and users_id = ?", symbol, id)
        if not sharesowned:
            return apology("No shares owned for this stock")
        if sharesowned[0]["shares"] < sharesnum:
            return apology("Number of shares exceeds what you own")
        else:
            sellvalue = int(sharesnum) * quote["price"]
            cashowned = db.execute("select cash from users where id = ?", id)
            newcash = cashowned[0]["cash"] + sellvalue
            db.execute("update users set cash = ? where id = ?", newcash, id)
            newshares = sharesowned[0]["shares"] - sharesnum
            db.execute("update indext set shares = ? where symbol = ? and users_id = ?", newshares, symbol, id)
            totalowned = db.execute("select total from indext where symbol = ? and users_id = ?", symbol, id)
            newtotal = int(totalowned[0]["total"] - sellvalue)
            db.execute("update indext set total = ? where symbol = ? and users_id = ?", newtotal, symbol, id)
            db.execute("insert into history (symbol, shares, price, h_id) values (?,?,?,?)", symbol, -1 * int(sharesnum), quote["price"], id)
            return redirect("/")

@app.route("/changepword", methods=["GET", "POST"])
@login_required
def changepword():
    if request.method == "GET":
        return render_template("changepword.html")
    else:
        newpassword = request.form.get("newpassword")
        confirm = request.form.get("confirmation")
        if not newpassword == confirm:
            return apology("New password and confirmed password don't match")
        hash = generate_password_hash(newpassword)
        db.execute("update users set hash = ? where id = ?", hash, session["user_id"])
        return redirect("/")