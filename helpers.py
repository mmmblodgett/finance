import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        response = requests.get(f"https://api.iextrading.com/1.0/stock/{urllib.parse.quote_plus(symbol)}/quote")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def portfolio(id, db):
    """Returns a dict of a user's owned shares and the quantity they own of each"""

    # Get the record of user's transactions
    record = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=id)

    # Build a dict of user's portfolio
    portfolio = {}
    for entry in record:
        # If user purchased a new stock add it to their portfolio
        if entry['symbol'] not in portfolio and entry['tran_type'] == 'BUY':
            portfolio[entry['symbol']] = entry['quant']
        # If user bought a stock they already own increase their holding
        elif entry['tran_type'] == 'BUY':
            portfolio[entry['symbol']] = portfolio[entry['symbol']] + entry['quant']
        # If user sold a stock they own decrease their holding
        elif entry['tran_type'] == 'SELL':
            portfolio[entry['symbol']] = portfolio[entry['symbol']] - entry['quant']
        # If user no longer has any shares delete the entry from their portfolio
        if portfolio[entry['symbol']] == 0:
            del portfolio[entry['symbol']]
    return portfolio