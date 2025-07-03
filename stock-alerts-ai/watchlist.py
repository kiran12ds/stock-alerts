# backend.py
from flask import Flask, render_template, request, redirect
from subscribers import load_subscribers, save_subscribers
from stock_reason import get_stock_reason

import smtplib
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf
import threading
import time
import json
import os

app = Flask(__name__, template_folder='templates')

LAST_PRICES_FILE = "last_prices.json"
THRESHOLD_PERCENT = 5  # Set to 5% movement
INTERVAL = 300  # Check every 5 minutes

EMAIL_SENDER = "2809kiran@gmail.com"
EMAIL_PASSWORD = "xxmfwzynuvkiuhxh"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

stock_changes_log = []

def load_last_prices():
    if os.path.exists(LAST_PRICES_FILE):
        with open(LAST_PRICES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_last_prices(data):
    with open(LAST_PRICES_FILE, 'w') as f:
        json.dump(data, f)

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = to
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print("[ERROR] SMTP Authentication failed. Check your email or app password.")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    table = pd.read_html(url)[0]
    return table['Symbol'].tolist()

def monitor_prices():
    tickers = get_sp500_tickers()
    last_prices = load_last_prices()
    global stock_changes_log

    while True:
        stock_changes_log.clear()
        for ticker in tickers:
            try:
                yf_ticker = yf.Ticker(ticker.replace('.', '-'))

                # Fetch 1-day intraday data at 5-minute interval
                data = yf_ticker.history(period="1d", interval="5m")

                if not data.empty and len(data) >= 2:
                    opening_price = data['Close'].iloc[0]
                    current_price = data['Close'].iloc[-1]
                    change = ((current_price - opening_price) / opening_price) * 100

                    if abs(change) >= THRESHOLD_PERCENT:
                        direction = "up" if change > 0 else "down"
                        reason = get_stock_reason(ticker, change, direction)
                        stock_changes_log.append({
                            'ticker': ticker,
                            'previous': round(opening_price, 2),
                            'current': round(current_price, 2),
                            'change': round(change, 2),
                            'reason': reason[:250] + ('...' if len(reason) > 250 else '')
                        })
                        for email in load_subscribers():
                            send_email(
                                email,
                                f"Alert: {ticker} moved {change:.2f}%",
                                f"{ticker} price changed from ${opening_price:.2f} to ${current_price:.2f} ({change:.2f}%)\n\nReason: {reason}"
                            )

                    last_prices[ticker] = current_price
            except Exception as e:
                print(f"[ERROR] Checking {ticker}: {e}")

        save_last_prices(last_prices)
        time.sleep(300)  # 5 minutes

@app.route('/', methods=['GET', 'POST'])
def index():
    subscribers = load_subscribers()
    if request.method == 'POST':
        email = request.form.get('email')
        action = request.form.get('action')
        if email:
            if action == 'subscribe' and email not in subscribers:
                subscribers.append(email)
            elif action == 'unsubscribe' and email in subscribers:
                subscribers.remove(email)
            save_subscribers(subscribers)
        return redirect('/')
    return render_template("watchlist-dashboard.html", subscribers=subscribers, threshold=THRESHOLD_PERCENT, stock_changes=stock_changes_log)

if __name__ == '__main__':
    threading.Thread(target=monitor_prices, daemon=True).start()
    app.run(debug=True)
