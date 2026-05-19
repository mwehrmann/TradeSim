CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    cash NUMERIC NOT NULL DEFAULT 10000.00
);

CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('buy', 'sell', 'deposit')),
    amount INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    time TEXT NOT NULL
);

CREATE INDEX idx_user
ON trades (user_id);
