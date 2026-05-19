import os
from cs50 import SQL
from datetime import datetime, timezone
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    holdings = db.execute(
        """
        SELECT
            symbol,
            SUM(
                CASE
                    WHEN action = 'buy' THEN amount
                    WHEN action = 'sell' THEN -amount
                    ELSE 0
                END
            ) AS [shares]
        FROM trades
        WHERE user_id = ?
        GROUP BY symbol
        HAVING
            SUM(
                CASE
                    WHEN action = 'buy' THEN amount
                    WHEN action = 'sell' THEN -amount
                    ELSE 0
                END
            ) > 0
        ORDER BY symbol ASC""",
        session["user_id"]
    )
    portfolio = []
    cash_dic = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash_dic[0]["cash"]
    total = cash
    for holding in holdings:
        row = lookup(holding["symbol"])
        row["shares"] = holding["shares"]
        value = holding["shares"] * row["price"]
        row["value"] = value
        portfolio.append(row)
        total += value
    return render_template("index.html", portfolio=portfolio, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a stock symbol", 400)
        symbol = symbol.strip().upper()
        shares = request.form.get("shares")
        if not shares:
            return apology("Please enter the amount of shares you want to buy", 400)
        try:
            shares = int(shares)
            if shares < 1:
                return apology("Please enter a positive integer of shares you want to buy", 400)
            else:
                stock = lookup(symbol)
                if stock:
                    # Check balance of user and buy share if balacne is sufficient, else return apology
                    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                    if cash[0]["cash"] >= (shares * stock["price"]):
                        db.execute(
                            "INSERT INTO trades (user_id, symbol, action, amount, price, time) VALUES (?, ?, ?, ?, ?, ?)",
                            session["user_id"],
                            stock["symbol"],
                            "buy",
                            shares,
                            stock["price"],
                            datetime.now(timezone.utc)
                        )
                        # Calculate and update new balance
                        new_balance = cash[0]["cash"] - shares * stock["price"]
                        db.execute(
                            "UPDATE users SET cash = ? WHERE id = ?",
                            new_balance,
                            session["user_id"]
                        )

                        # Redirect user to home page
                        return redirect("/")
                    else:
                        return apology("Insufficient funds", 400)
                else:
                    return apology("Please enter a valid stock symbol", 400)
        except ValueError:
            return apology("Please enter a positive integer of shares you want to buy", 400)

    else:
        return render_template("buy.html")

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        amount = request.form.get("amount")
        if not amount:
            return apology("Please enter a amount", 400)
        try:
            amount = int(amount)
            if amount <= 0:
                return apology("Please enter a positive amount", 400)
            db.execute(
                """
                UPDATE users
                SET cash = cash + ?
                WHERE id = ?""",
                amount,
                session["user_id"])
            db.execute("INSERT INTO trades (user_id, symbol, action, amount, price, time) VALUES (?, ?, ?, ?, ?, ?)",
                            session["user_id"],
                            "USD",
                            "deposit",
                            amount,
                            1,
                            datetime.now(timezone.utc)
                        )
            return redirect("/")
        except ValueError:
            return apology("Please enter a positive integer of the amount you would like to deposit", 400)
    else:
        return render_template("deposit.html")


@app.route("/history")
@login_required
def history():
    history = db.execute(
        """
        SELECT
            symbol,
            action,
            amount,
            price,
            time
        FROM trades
        WHERE user_id = ?
        ORDER BY time DESC
        """,
        session["user_id"]
    )
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a stock symbol", 400)
        symbol = symbol.strip().upper()
        stock = lookup(symbol)
        if stock:
            return render_template("quoted.html", stock=stock)
        else:
            return apology("Please enter a valid stock symbol", 400)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        # verify that user submits a username
        username = request.form.get("username")
        if not username:
            return apology("Please provide a username", 400)

        # verify that user submits a password
        password = request.form.get("password")
        if not password:
            return apology("Please provide a password", 400)

        # verify that user sumbits a password confirmation
        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("Please confirm your password", 400)

        # verify that password matches password confirmation
        if password != confirmation:
            return apology("Password must match password confirmation", 400)

        # if user submits password and password matches password confirmation insert into database, exception if username already exists
        if username and (password == confirmation):
            try:
                password_hash = generate_password_hash(password)
                db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                           username, password_hash)
                flash("Registration successful!")
                return redirect("/login")
            except ValueError:
                return apology("Username already exists", 400)
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    holdings = db.execute(
        """
        SELECT
            symbol,
            SUM(
                CASE
                    WHEN action = 'buy' THEN amount
                    WHEN action = 'sell' THEN -amount
                    ELSE 0
                END
            ) AS [shares]
        FROM trades
        WHERE user_id = ?
        GROUP BY symbol
        HAVING
            SUM(
                CASE
                    WHEN action = 'buy' THEN amount
                    WHEN action = 'sell' THEN -amount
                    ELSE 0
                END
            ) > 0
        ORDER BY symbol ASC""",
        session["user_id"]
    )
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a stock symbol", 400)
        symbol = symbol.strip().upper()
        shares_to_sell = request.form.get("shares")
        if not shares_to_sell:
            return apology("Please enter the amount of shares you want to sell", 400)
        try:
            shares_to_sell = int(shares_to_sell)
            if shares_to_sell < 1:
                return apology("Please enter a positive integer of shares you want to sell", 400)
            else:
                stock = lookup(symbol)
                if not stock:
                    return apology("Please enter a valid stock symbol", 400)
                for row in holdings:
                    if row["symbol"] == stock["symbol"]:
                        shares_held = row["shares"]
                        if shares_held >= shares_to_sell:
                            db.execute(
                                "INSERT INTO trades (user_id, symbol, action, amount, price, time) VALUES (?, ?, ?, ?, ?, ?)",
                                session["user_id"],
                                stock["symbol"],
                                "sell",
                                shares_to_sell,
                                stock["price"],
                                datetime.now(timezone.utc)
                            )
                            cash = db.execute(
                                "SELECT cash FROM users WHERE id = ?", session["user_id"])
                            new_balance = cash[0]["cash"] + shares_to_sell * stock["price"]
                            db.execute(
                                "UPDATE users SET cash = ? WHERE id = ?",
                                new_balance,
                                session["user_id"]
                            )
                            return redirect("/")
                        else:
                            return apology("Insufficient holdings", 400)
                return apology("Stock not in portfolio", 400)

        except ValueError:
            return apology("Please enter a positive integer of shares you want to sell", 400)
    """Sell shares of stock"""
    return render_template("sell.html", holdings=holdings)
