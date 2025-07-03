# stock_reason.py
import os
from datetime import datetime, timezone
import google.generativeai as genai
from transformers import pipeline
import tensorflow as tf
from dotenv import load_dotenv

tf.get_logger().setLevel('ERROR')
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

cache = {}
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def get_stock_reason(ticker, change=None, direction=None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"{ticker}_{today}"
    if cache_key in cache:
        return cache[cache_key]
    direction_phrase = "increased" if direction == "up" else "decreased"

    # Prompt for Gemini
    prompt = (
        f"Act as a financial analyst. A stock with ticker '{ticker}' has {direction_phrase} approximately {change}% today. "
        "Based on current market trends, economic conditions, industry sentiment, or recent events or earnings, analyze and hypothesize the potential cause. "
        "Also assume insider data. Return a concise institutional-grade explanation in tabular format."
    )

    try:
        response = model.generate_content(prompt)
        summary = response.text.strip()
        cache[cache_key] = summary
        return summary

    except Exception as e:
        print(f"[ERROR] Gemini failed: {e}")
        # Fallback: Construct a pseudo-article as context
        fallback_context = (
            f"{ticker} stock experienced a significant {threshold_percent}% decline in price today. "
            f"This movement could be related to recent economic indicators, sector rotation, or company-specific developments. "
            f"Market participants may be reacting to news involving interest rates, inflation expectations, or geopolitical uncertainty. "
            f"Investors are assessing potential risks in the {ticker} sector."
        )

        try:
            input_length = len(fallback_context.split())
            max_len = min(120, int(input_length * 0.7))
            if input_length < 10:
                return "Not enough data to summarize effectively."

            summary = summarizer(
                fallback_context,
                max_length=max_len,
                min_length=20,
                do_sample=False
            )[0]["summary_text"]

            print(f"[INFO] Fallback summary used for {ticker}")
            cache[cache_key] = summary
            return summary

        except Exception as hf_error:
            print(f"[ERROR] Fallback summarization failed: {hf_error}")
            return f"No AI-generated reason available for {ticker} today."
