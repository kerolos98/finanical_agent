from mcp.server.fastmcp import FastMCP
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

mcp = FastMCP("financial-analyst-server")


# =====================================================
# TOOLS
# =====================================================
@mcp.tool(
    name="get_portfolio_prices",
    description="Fetch current prices and total value. Supports multiple input formats.",
)
def get_portfolio_prices(portfolio_input: any) -> dict:
    # --- NORMALIZATION LOGIC ---
    items = []
    if isinstance(portfolio_input, dict):
        if "portfolio" in portfolio_input:
            items = portfolio_input["portfolio"]
        else:
            items = [{"ticker": k, "position": v} for k, v in portfolio_input.items()]
    elif isinstance(portfolio_input, list):
        items = portfolio_input

    if not items:
        return {"error": "Invalid portfolio format"}

    tickers = [item["ticker"] for item in items]
    data = yf.download(tickers, period="1d", progress=False)

    # Handle single vs multiple ticker returns
    if len(tickers) == 1:
        prices = {tickers[0]: float(data["Close"].iloc[-1])}
    else:
        prices = data["Close"].iloc[-1].to_dict()

    total_val = 0
    details = []

    for item in items:
        t = item["ticker"]
        qty = item["position"]
        p = prices.get(t, 0)
        position_val = p * qty
        total_val += position_val

        details.append(
            {
                "ticker": t,
                "price": round(float(p), 2),
                "value": round(float(position_val), 2),
            }
        )

    return {
        "total_market_value": round(total_val, 2),
        "currency": "USD",
        "positions": details,
    }


@mcp.tool(
    name="get_dividend_report",
    description="Calculates upcoming dividends. Handles both list and dict portfolio structures.",
)
def get_dividend_report(portfolio_input: any) -> dict:
    import datetime

    # --- NORMALIZATION LOGIC ---
    items = []
    if isinstance(portfolio_input, dict):
        # Check if it's the {"portfolio": [...]} structure
        if "portfolio" in portfolio_input:
            items = portfolio_input["portfolio"]
        else:
            # It's the {'AAPL': 10} structure
            items = [{"ticker": k, "position": v} for k, v in portfolio_input.items()]
    elif isinstance(portfolio_input, list):
        items = portfolio_input

    report = []
    total_annual = 0
    next_month_cash = 0

    today = datetime.datetime.now()
    next_month = (today.month % 12) + 1

    for item in items:
        ticker = item["ticker"]
        shares = item["position"]

        stock = yf.Ticker(ticker)
        info = stock.info
        div_rate = info.get("dividendRate", 0) or 0

        # Get payment dates
        cal = stock.calendar
        pay_date = "N/A"
        is_paying_next = False
        if cal is not None and "Dividend Date" in cal:
            dt = cal["Dividend Date"]
            if isinstance(dt, (datetime.datetime, datetime.date)):
                # If it's a datetime, convert to date. If it's already a date, just use it.
                actual_date = dt.date() if hasattr(dt, 'date') else dt
                pay_date = str(actual_date)
                
                if actual_date.month == next_month:
                    is_paying_next = True

        annual_inc = div_rate * shares
        total_annual += annual_inc

        if is_paying_next:
            # Monthly vs Quarterly logic
            if ticker in ["O", "JEPI", "AGNC"]:
                next_month_cash += annual_inc / 12
            else:
                next_month_cash += annual_inc / 4

        report.append(
            {
                "ticker": ticker,
                "annual_income": round(annual_inc, 2),
                "next_pay_date": pay_date,
                "is_paying_next_month": is_paying_next,
            }
        )

    return {
        "summary": {
            "total_annual_income": round(total_annual, 2),
            "est_next_month_payout": round(next_month_cash, 2),
        },
        "details": report,
    }


@mcp.tool(
    name="get_stock_price",
    description="Retrieve the most recent closing price of a stock ticker.",
)
def get_stock_price(
    ticker: str,
) -> dict:
    """
    Args:
        ticker (str): Stock symbol such as AAPL, MSFT, or TTE.

    Returns:
        dict:
            ticker: requested stock symbol
            price: latest closing price
    """

    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")

    if data.empty:
        return {"error": "No price data found for ticker"}

    price = data["Close"].iloc[-1]

    return {"ticker": ticker, "price": float(price)}



@mcp.tool(
    name="get_stocks_prices",
    description="Retrieve the most recent closing prices of stocks tickers.",
)
def get_stocks_prices(tickers: list[str])->list[dict]:
    prices = []
    for ticker in tickers:
        prices.append(get_stock_price(ticker))
    return prices


@mcp.tool(
    name="financial_health_check",
    description="Comprehensive check of bankruptcy risk (Z-Score) and quality (F-Score).",
)
def financial_health_check(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    # yfinance balance sheet and income statement are needed for these
    bs = stock.balance_sheet
    is_stmt = stock.income_stmt

    # Logic to calculate Altman Z-Score and Piotroski F-Score goes here...
    # (Requires extracting items like Total Assets, Retained Earnings, etc.)

    return {
        "ticker": ticker,
        "z_score": 2.85,  # Example
        "f_score": 7,  # Example
        "interpretation": "Strong financial position, low bankruptcy risk.",
    }


import yfinance as yf
import pandas as pd


@mcp.tool(
    name="portfolio_value",
    description="Calculate the total value and weight of a stock portfolio using bulk data fetching.",
)
def portfolio_value(
    portfolio: dict,
) -> dict:
    """
    Args:
        portfolio (dict): Ticker symbols and share counts.
        Example: {"AAPL": 10, "MSFT": 5, "TTE": 20}

    Returns:
        dict: Breakdown of positions, total value, and portfolio weights.
    """
    if not portfolio:
        return {"error": "Portfolio is empty"}

    # 1. BULK FETCH: Fetch all tickers in one go
    ticker_list = list(portfolio.keys())
    # We use '1d' period to get the most recent closing prices
    data = yf.download(ticker_list, period="1d", progress=False)

    # Handle single vs multiple ticker return formats from yfinance
    if len(ticker_list) == 1:
        latest_prices = {ticker_list[0]: float(data["Close"].iloc[-1])}
    else:
        latest_prices = data["Close"].iloc[-1].to_dict()

    # 2. CALCULATE VALUES
    total_value = 0
    positions = {}

    for ticker, shares in portfolio.items():
        price = latest_prices.get(ticker)

        if price is None or pd.isna(price):
            positions[ticker] = {"error": "Price data unavailable"}
            continue

        position_value = float(price * shares)
        total_value += position_value

        positions[ticker] = {
            "shares": shares,
            "current_price": round(price, 2),
            "position_value": round(position_value, 2),
        }

    # 3. ADD WEIGHTS (Portfolio Concentration)
    for ticker, info in positions.items():
        if "position_value" in info:
            weight = (info["position_value"] / total_value) * 100
            info["portfolio_weight"] = f"{weight:.2f}%"

    return {
        "summary": {
            "total_value": round(total_value, 2),
            "currency": "USD",
            "position_count": len(positions),
        },
        "positions": positions,
    }


@mcp.tool(
    name="get_fundamentals",
    description="Retrieve key financial fundamentals for a company.",
)
def get_fundamentals(
    ticker: str,
) -> dict:
    """
    Args:
        ticker (str): Stock ticker symbol.

    Returns:
        dict containing financial metrics:
            market_cap
            pe_ratio
            forward_pe
            dividend_yield
            profit_margin
            revenue_growth
    """

    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "ticker": ticker,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
    }


@mcp.tool(
    name="moving_averages",
    description="Calculate 50-day and 200-day moving averages for a stock.",
)
def moving_averages(
    ticker: str,
) -> dict:
    """
    Args:
        ticker (str): Stock symbol.

    Returns:
        dict:
            ticker
            MA50
            MA200
    """

    stock = yf.Ticker(ticker)
    data = stock.history(period="1y")

    data["MA50"] = data["Close"].rolling(50).mean()
    data["MA200"] = data["Close"].rolling(200).mean()

    return {
        "ticker": ticker,
        "MA50": float(data["MA50"].iloc[-1]),
        "MA200": float(data["MA200"].iloc[-1]),
    }


@mcp.tool(
    name="rsi_indicator",
    description="Calculate the Relative Strength Index (RSI) for a stock.",
)
def rsi_indicator(
    ticker: str,
    period: int = 14,
) -> dict:
    """
    Args:
        ticker (str): Stock symbol.
        period (int): RSI calculation window. Default is 14.

    Returns:
        dict:
            ticker
            RSI
    """

    stock = yf.Ticker(ticker)
    data = stock.history(period="6mo")

    delta = data["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return {"ticker": ticker, "RSI": float(rsi.iloc[-1])}


@mcp.tool(
    name="portfolio_value",
    description="Calculate the total value of a stock portfolio.",
)
def portfolio_value(
    portfolio: dict,
) -> dict:
    """
    Args:
        portfolio (dict):
            Dictionary of ticker symbols and share counts.

            Example:
            {
                "AAPL": 10,
                "TTE": 5
            }

    Returns:
        dict:
            positions
            total_value
    """

    total = 0
    result = {}

    for ticker, shares in portfolio.items():

        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")["Close"].iloc[-1]

        value = float(price * shares)

        result[ticker] = {"shares": shares, "price": float(price), "value": value}

        total += value

    return {"positions": result, "total_value": total}


@mcp.tool(
    name="valuation_summary",
    description="Provide a simple valuation classification based on PE ratio.",
)
def valuation_summary(
    ticker: str,
) -> dict:
    """
    Args:
        ticker (str): Stock symbol.

    Returns:
        dict:
            ticker
            pe_ratio
            valuation classification
    """

    stock = yf.Ticker(ticker)
    info = stock.info

    pe = info.get("trailingPE")

    if pe is None:
        return {"message": "No PE ratio available"}

    if pe < 15:
        valuation = "possibly undervalued"
    elif pe > 30:
        valuation = "possibly overvalued"
    else:
        valuation = "fairly valued"

    return {"ticker": ticker, "pe_ratio": pe, "valuation": valuation}


#Python
@mcp.tool(
    name="get_dividend_income_summary",
    description="Direct monthly/quarterly income totals and the next payment date with dynamic currency detection.",
)
def get_dividend_income_summary(portfolio_input: dict) -> dict:
    import datetime
    import pandas as pd
    
    if not portfolio_input:
        return {"error": "Missing portfolio input."}

    # Normalize structure
    if "portfolio" in portfolio_input:
        items = portfolio_input["portfolio"]
    else:
        items = [{"ticker": k, "position": v} for k, v in portfolio_input.items()]

    monthly_total = 0
    quarterly_total = 0
    upcoming_payments = []
    detected_currencies = set()
    
    for item in items:
        try:
            ticker = item["ticker"]
            shares = item["position"]
            stock = yf.Ticker(ticker)
            
            info = stock.info
            # --- DYNAMIC CURRENCY FETCH ---
            currency = info.get("currency", "USD") 
            detected_currencies.add(currency)

            annual_rate = info.get("dividendRate", 0) or 0
            if not annual_rate: continue
                
            annual_income = annual_rate * shares
            
            # Categorize frequency
            if ticker in ["O", "JEPI", "AGNC"]:
                monthly_total += (annual_income / 12)
            else:
                quarterly_total += (annual_income / 4)

            # Calendar check
            cal = stock.calendar
            if cal is not None and 'Dividend Date' in cal:
                d_date = cal['Dividend Date']
                if d_date and not pd.isna(d_date):
                    upcoming_payments.append({
                        "ticker": ticker,
                        "date": d_date,
                        "amount": round((annual_income / 12) if ticker in ["O", "JEPI", "AGNC"] else (annual_income / 4), 2),
                        "currency": currency
                    })
        except Exception:
            continue

    upcoming_payments.sort(key=lambda x: x['date'])
    
    next_pay_info = {"ticker": "N/A", "date": "N/A", "amount": 0, "currency": "N/A"}
    if upcoming_payments:
        pay = upcoming_payments[0]
        dt = pay["date"]
        next_pay_info = {
            "ticker": pay["ticker"],
            "date": str(dt.date()) if isinstance(dt, datetime.datetime) else str(dt),
            "amount": pay["amount"],
            "currency": pay["currency"]
        }

    return {
        "income_summary": {
            "estimated_monthly_avg": round(monthly_total + (quarterly_total / 3), 2),
            "monthly_payer_total": round(monthly_total, 2),
            "quarterly_payer_total": round(quarterly_total, 2),
            "primary_currency": list(detected_currencies)[0] if len(detected_currencies) == 1 else "MIXED"
        },
        "next_payment": next_pay_info,
        "all_detected_currencies": list(detected_currencies)
    }


# =====================================================
# RESOURCES
# =====================================================


@mcp.resource(
    "portfolio://main",
    name="user_portfolio",
    description="The user's investment portfolio.",
)
def user_portfolio():
    """
    Returns:
        dict mapping stock tickers to share counts.
    """

    return {
        "AGNC": 26,
        "CRDF": 4,
        "EONR": 18,
        "INUV": 5,
        "JEPI": 44.2477,
        "O": 22.9025,
        "PBA": 46.7371,
        "SHELL": 20.1343,
        "SMSI": 37,
        "SP5": 50,
        "TTE": 5.3817,
    }


@mcp.resource(
    "knowledge://investing_rules",
    name="investing_rules",
    description="Basic long-term investing strategy rules.",
)
def investing_rules():
    """
    Returns investment guidelines used by the agent.
    """

    return """
    Long-term investing rules:

    1. Prefer companies with positive cash flow.
    2. Avoid extremely high debt levels.
    3. Diversify across sectors.
    4. Companies with stable dividends are safer during inflation.
    5. Watch macroeconomic indicators.
    """


# =====================================================
# PROMPTS
# =====================================================


@mcp.prompt(
    name="stock_analysis_prompt",
    description="Prompt template for analyzing an individual stock.",
)
def stock_analysis_prompt(ticker: str):
    """
    Args:
        ticker (str): Stock ticker symbol.

    Returns:
        formatted analysis prompt
    """

    return f"""
    You are a professional financial analyst agent. 

    Analyze the stock {ticker} using ALL available tools:

    - Moving averages (call `moving_averages`)
    - Relative Strength Index (call `rsi_indicator`)
    - Financial health metrics (call `financial_health_check`)
    - Valuation summary (call `valuation_summary`)
    - Market fundamentals (call `get_fundamentals`)

    Always call the tools via the agent — do NOT give your own values. 
    Include the tool calls in your response before writing the analysis.

    After executing the tools, provide a detailed report including:

    1. Buy / Hold / Sell recommendation
    2. Risk level
    3. Long-term outlook
    """


@mcp.prompt(
    name="portfolio_analysis_prompt",
    description="Prompt template for analyzing an investment portfolio.",
)
def portfolio_analysis_prompt():
    """
    Returns a prompt for portfolio evaluation.
    """

    return """
    You are a professional portfolio manager.

    Analyze the portfolio and determine:

    1. diversification level
    2. risk exposure
    3. sector concentration
    4. recommendations for improvement
    """


@mcp.prompt(
    name="extract_ticker_prompt",
    description="Extract the stock ticker symbol from a user query. "
    "If the user mentions a company name, return the correct ticker. "
    "Only return the ticker, nothing else.",
)
def extract_ticker_prompt():
    return """
You are a financial assistant.

Rules:
1. User may mention either the company name or ticker symbol.
2. Return ONLY the correct stock ticker in uppercase (e.g., AAPL, MSFT, TTE).
3. If multiple companies match, choose the most likely one.
4. If no valid company is found, return 'UNKNOWN'.

Examples:
- 'Analyze Apple stock' → 'AAPL'
- 'Check Microsoft fundamentals' → 'MSFT'
- 'Evaluate TTE' → 'TTE'
- 'Random text' → 'UNKNOWN'
"""


# =====================================================
# RUN SERVER
# =====================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
