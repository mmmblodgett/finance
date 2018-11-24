import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, portfolio

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["lookup"] = lookup

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get a dict of the user's holdings
    port = portfolio(session['user_id'], db)

    # Get the user's current cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])[0]['cash']

    # Get the user's total portfolio valuation
    total = cash
    for symbol in port:
        total += lookup(symbol)['price'] * port[symbol]
    return render_template("index.html", cash=cash, portfolio=port, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure stock symbol was entered
        if not request.form.get("symbol"):
            return apology("missing symbol")

        # Ensure quantity of shares was entered
        if not request.form.get("shares"):
            return apology("must enter number of shares")

        # Ensure a valid symbol was entered
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")

        # Ensure shares is a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer")
        if not request.form.get("shares").isdigit() or not shares > 0:
            return apology("shares must be a positive integer")

        # Get user's cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])[0]['cash']

        # Ensure user has enough cash for purchase
        if (quote['price'] * shares) > cash:
            return apology(f"You cannot afford {shares} shares of {quote['symbol']}")

        # Subtract the cost from user's cash
        db.execute("UPDATE users SET cash = cash - :cost WHERE id = :id", cost=(quote['price'])*shares, id=session['user_id'])

        # Create a transaction record
        db.execute("INSERT INTO transactions (user_id, tran_type, symbol, price, quant) VALUES(:id, 'BUY', :symbol, :price, :quant)",
                   id=session['user_id'], symbol=quote['symbol'], price=quote['price'], quant=shares)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    # Get the username entered
    username = request.args.get("username")
    # Get a list of all usernames already in use
    users = [user['username'] for user in db.execute("SELECT username FROM users")]
    return jsonify(not username in users)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Get user's transaction record
    record = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=session['user_id'])

    return render_template("history.html", record=record)


@app.route("/leaderboard")
def leaderboard():
    """Show a leaderboard of all users"""

    # Get a dict of all registered users
    users = db.execute("SELECT id, username, cash FROM users")

    # Create a dict with each user's total profile valuation
    leader = {}
    for user in users:
        # Get the user's cash
        leader[user['username']] = user['cash']
        port = portfolio(user['id'], db)
        # Add in the valuation of their stocks
        for symbol in port:
            leader[user['username']] += lookup(symbol)['price'] * port[symbol]

    # Swap the valuation with the username
    leaders = [[leader[user], user] for user in leader]

    # Sort the users from highest valuation to lowest
    leaders.sort(reverse=True)

    return render_template("leaderboard.html", leaders=leaders)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    if request.method == "POST":

        # Ensure a symbol was entered
        if not request.form.get("symbol"):
            return apology("missing symbol")

        # Ensure the symbol is valid
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")

        # Return the quote
        return render_template("quote2.html", quote=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password")

        # Ensure password confirmation matches
        elif not request.form.get("confirmation") == request.form.get("password"):
            return apology("passwords must match")

        else:

            # Create a password hash
            hash = generate_password_hash(request.form.get("password"))

            # Add the user to users
            result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                username=request.form.get("username"), hash=hash)
            if not result:
                return apology("username already taken")

        # Log the user in
        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Ensure a symbol was entered
        if not request.form.get("symbol"):
            return apology("missing symbol")

        # Ensure a number of shares was entered
        if not request.form.get("shares"):
            return apology("must enter number of shares")

        # Ensure the symbol is valid
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")

        # Ensure shares is a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer")
        if not request.form.get("shares").isdigit() or not shares > 0:
            return apology("shares must be a positive integer")

        # Ensure the user has enough shares to sell
        if shares > portfolio(session['user_id'], db)[request.form.get("symbol")]:
            return apology("cannot sell more shares than you own")

        # Add the sale price to user's cash
        db.execute("UPDATE users SET cash = cash + :cost WHERE id = :id", cost=(quote['price'])*shares, id=session['user_id'])

        # Add a transaction record
        db.execute("INSERT INTO transactions (user_id, tran_type, symbol, price, quant) VALUES(:id, 'SELL', :symbol, :price, :quant)",
                   id=session['user_id'], symbol=quote['symbol'], price=quote['price'], quant=shares)

        return redirect("/")
    else:

        # Get the user's portfolio
        port = portfolio(session['user_id'], db)

        return render_template("sell.html", portfolio=port)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
