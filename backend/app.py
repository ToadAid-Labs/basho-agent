"""
Main Flask Application

This module provides the main Flask application for the crypto trading bot.
"""

from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session
from flask_cors import CORS
from typing import Optional
import os
import sys
import logging
import threading
import time
from functools import wraps
from urllib.parse import parse_qs, urlparse

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.database import Base, init_db, SessionLocal, User, Trade
from backend.api import api_bp, initialize_paper_trading_for_user, get_current_prices
from backend.portfolio_dashboard import Portfolio, PortfolioTracker
from backend.prediction_tracker import PredictionLedger
from backend.trend_forge_service import clear_forge_alerts, evaluate_due_predictions, list_forge_alerts, process_due_watchlist, record_live_prediction, run_live_backtest
from backend.trend_prediction_ledger import TrendPredictionLedger
from backend.trend_watchlist import TrendForgeWatchlist
from memory.wisdom import WisdomStore

# Agent imports
from core.agent import Agent
from core.auth import (
    build_google_web_flow,
    build_openai_codex_oauth_url,
    exchange_openai_codex_code,
    save_google_credentials,
    save_openai_api_key,
    save_openai_codex_credentials,
)
from core.provider import get_provider

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configure CORS
CORS(app)

# Register blueprint
app.register_blueprint(api_bp)

# Configure app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JSON_SORT_KEYS'] = False
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'admin123')

# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Initialize portfolio tracker
portfolio_tracker = PortfolioTracker()

# Global Agent instance for the web session
web_agent = None

def reset_web_agent():
    """Force the web session to pick up updated provider credentials."""
    global web_agent
    web_agent = None

def get_web_agent():
    global web_agent
    if web_agent is None:
        provider = get_provider()
        # Initialize an agent session specifically for the web UI
        web_agent = Agent(provider=provider, sid="web_dashboard_session")
    return web_agent

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', url_for('index'))
    if request.method == 'POST':
        password = request.form.get('password')
        if password == DASHBOARD_PASSWORD:
            session['logged_in'] = True
            return redirect(next_url)
        return render_template('login.html', error='Invalid password', next=next_url)
    return render_template('login.html', next=next_url)

@app.route('/auth/google')
@login_required
def google_auth():
    """Start the Google OAuth flow for Gemini credentials."""
    redirect_uri = os.getenv(
        'GOOGLE_OAUTH_REDIRECT_URI',
        url_for('google_auth_callback', _external=True)
    )
    flow = build_google_web_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    session['google_oauth_state'] = state
    return redirect(authorization_url)

@app.route('/auth/google/callback')
@login_required
def google_auth_callback():
    """Complete Google OAuth and store credentials for Gemini."""
    state = session.pop('google_oauth_state', None)
    if not state or state != request.args.get('state'):
        flash('Google authentication failed: invalid OAuth state.', 'error')
        return redirect(url_for('index'))

    try:
        redirect_uri = os.getenv(
            'GOOGLE_OAUTH_REDIRECT_URI',
            url_for('google_auth_callback', _external=True)
        )
        flow = build_google_web_flow(redirect_uri, state=state)
        flow.fetch_token(authorization_response=request.url)
        save_google_credentials(flow.credentials)
        reset_web_agent()
        flash('Google authentication complete. Gemini is now the active provider.', 'success')
    except Exception as exc:
        logger.exception("Google OAuth callback failed")
        flash(f'Google authentication failed: {exc}', 'error')

    return redirect(url_for('index'))

@app.route('/auth/openai', methods=['GET', 'POST'])
@login_required
def openai_auth():
    """Save an OpenAI API key from the web UI."""
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        if not api_key:
            return render_template('provider_auth.html', error='OpenAI API key is required.')

        save_openai_api_key(api_key)
        reset_web_agent()
        flash('OpenAI API key saved. OpenAI is now the active provider.', 'success')
        return redirect(url_for('index'))

    return render_template('provider_auth.html')

@app.route('/auth/openai/oauth')
@login_required
def openai_oauth():
    """Start ChatGPT/Codex OAuth using the public Codex PKCE client."""
    redirect_uri = os.getenv('OPENAI_CODEX_REDIRECT_URI')
    authorization_url, state, verifier, redirect_uri = build_openai_codex_oauth_url(redirect_uri)
    session['openai_oauth_state'] = state
    session['openai_oauth_verifier'] = verifier
    session['openai_oauth_redirect_uri'] = redirect_uri
    return redirect(authorization_url)

@app.route('/auth/callback')
@app.route('/auth/openai/oauth/callback')
@login_required
def openai_oauth_callback():
    """Complete ChatGPT/Codex OAuth when this Flask app receives the callback."""
    return complete_openai_oauth(request.args.get('code'), request.args.get('state'))

@app.route('/auth/openai/oauth/complete', methods=['POST'])
@login_required
def openai_oauth_complete():
    """Complete ChatGPT/Codex OAuth from a pasted callback URL or code."""
    pasted_value = request.form.get('callback_value', '').strip()
    code = pasted_value
    state = None

    if pasted_value.startswith('http://') or pasted_value.startswith('https://'):
        query = parse_qs(urlparse(pasted_value).query)
        code = query.get('code', [''])[0]
        state = query.get('state', [None])[0]

    return complete_openai_oauth(code, state)

def complete_openai_oauth(code: str | None, state: str | None):
    """Validate OAuth state, exchange code, and save ChatGPT/Codex credentials."""
    expected_state = session.pop('openai_oauth_state', None)
    verifier = session.pop('openai_oauth_verifier', None)
    redirect_uri = session.pop('openai_oauth_redirect_uri', None)

    if not code:
        flash('OpenAI OAuth failed: missing authorization code.', 'error')
        return redirect(url_for('openai_auth'))
    if state and state != expected_state:
        flash('OpenAI OAuth failed: invalid OAuth state.', 'error')
        return redirect(url_for('openai_auth'))
    if not verifier or not redirect_uri:
        flash('OpenAI OAuth failed: start the sign-in flow again before pasting a code.', 'error')
        return redirect(url_for('openai_auth'))

    try:
        tokens = exchange_openai_codex_code(code, verifier, redirect_uri)
        save_openai_codex_credentials(tokens)
        flash('OpenAI Codex OAuth complete. ChatGPT/Codex tokens were saved.', 'success')
    except Exception as exc:
        logger.exception("OpenAI OAuth callback failed")
        flash(f'OpenAI OAuth failed: {exc}', 'error')

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Serve the portfolio dashboard."""
    return render_template('dashboard.html')

@app.route('/api/portfolio/<int:telegram_id>')
@login_required
def get_portfolio(telegram_id: int):
    """Get portfolio data for a user."""
    try:
        data = portfolio_tracker.get_portfolio_data(telegram_id)
        return jsonify(data)
    except Exception as e:
        logger.exception("Error in get_portfolio")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/predictions/<symbol>')
@login_required
def get_predictions(symbol: str):
    """Get AI price predictions for a symbol."""
    try:
        data = portfolio_tracker.get_ai_predictions(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.exception("Error in get_predictions")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/prediction-accuracy')
@login_required
def get_prediction_accuracy_api():
    """Get prediction accuracy summary for dashboard display."""
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', default=100, type=int)
    try:
        ledger = PredictionLedger()
        evaluated = ledger.evaluate_due(
            lambda sym: get_current_prices().get(sym.upper()),
            symbol=symbol,
            evaluate_all=False,
        )
        summary = ledger.summary(symbol=symbol, limit=limit)
        summary['newly_evaluated'] = len(evaluated)
        return jsonify(summary)
    except Exception as e:
        logger.exception("Error in get_prediction_accuracy_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/ledger')
@login_required
def get_forge_ledger_summary_api():
    """Get Trend Prediction Forge ledger accuracy summary."""
    asset = request.args.get('asset')
    limit = request.args.get('limit', default=100, type=int)
    try:
        evaluated = evaluate_due_predictions(asset=asset, evaluate_all=False)
        summary = TrendPredictionLedger().summary(asset=asset, limit=limit)
        summary['newly_evaluated'] = len(evaluated)
        return jsonify(summary)
    except Exception as e:
        logger.exception("Error in get_forge_ledger_summary_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/record', methods=['POST'])
@login_required
def record_forge_prediction_api():
    """Record a live Trend Prediction Forge forecast."""
    data = request.get_json() or {}
    asset = data.get('asset')
    if not asset and not data.get('token_address'):
        return jsonify({'error': 'asset or token_address is required'}), 400
    try:
        record = record_live_prediction(
            asset=asset,
            token_address=data.get('token_address'),
            chain=data.get('chain', 'base'),
            horizon=data.get('horizon', '24h'),
            mode=data.get('mode', 'composite'),
            historical_limit=int(data.get('historical_limit', 72)),
        )
        return jsonify(record)
    except Exception as e:
        logger.exception("Error in record_forge_prediction_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/evaluate', methods=['POST'])
@login_required
def evaluate_forge_predictions_api():
    """Evaluate due or selected Trend Prediction Forge ledger records."""
    data = request.get_json() or {}
    try:
        evaluated = evaluate_due_predictions(
            asset=data.get('asset'),
            evaluate_all=bool(data.get('evaluate_all', False)),
        )
        return jsonify({'evaluated': len(evaluated), 'records': evaluated})
    except Exception as e:
        logger.exception("Error in evaluate_forge_predictions_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/backtest', methods=['POST'])
@login_required
def forge_backtest_api():
    """Run a Trend Prediction Forge backtest."""
    data = request.get_json() or {}
    asset = data.get('asset')
    if not asset:
        return jsonify({'error': 'asset is required for historical backtests'}), 400
    try:
        result = run_live_backtest(
            asset=asset,
            horizon=data.get('horizon', '24h'),
            mode=data.get('mode', 'composite'),
            lookback=int(data.get('lookback', 72)),
            stride=int(data.get('stride', 6)),
            limit=int(data.get('limit', 500)),
        )
        status = 400 if result.get('error') else 200
        return jsonify(result), status
    except Exception as e:
        logger.exception("Error in forge_backtest_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/watchlist')
@login_required
def forge_watchlist_api():
    """List Trend Prediction Forge watchlist entries."""
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    user_id = request.args.get('user_id', type=int)
    try:
        return jsonify(TrendForgeWatchlist().list(active_only=active_only, user_id=user_id))
    except Exception as e:
        logger.exception("Error in forge_watchlist_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/watchlist', methods=['POST'])
@login_required
def add_forge_watch_api():
    """Add a Trend Prediction Forge watchlist entry."""
    data = request.get_json() or {}
    if not data.get('asset') and not data.get('token_address'):
        return jsonify({'error': 'asset or token_address is required'}), 400
    try:
        watch = TrendForgeWatchlist().add(
            asset=data.get('asset'),
            token_address=data.get('token_address'),
            chain=data.get('chain', 'base'),
            horizons=data.get('horizons'),
            modes=data.get('modes'),
            interval_minutes=int(data.get('interval_minutes', 60)),
            thresholds=data.get('thresholds'),
            user_id=data.get('user_id'),
        )
        return jsonify(watch)
    except Exception as e:
        logger.exception("Error in add_forge_watch_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/watchlist/<watch_id>', methods=['DELETE'])
@login_required
def delete_forge_watch_api(watch_id: str):
    """Delete a Trend Prediction Forge watchlist entry."""
    try:
        deleted = TrendForgeWatchlist().delete(watch_id)
        return jsonify({'deleted': deleted})
    except Exception as e:
        logger.exception("Error in delete_forge_watch_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/watchlist/run', methods=['POST'])
@login_required
def run_forge_watchlist_api():
    """Process due or all Trend Prediction Forge watches."""
    data = request.get_json() or {}
    try:
        result = process_due_watchlist(force=bool(data.get('force', False)))
        return jsonify(result)
    except Exception as e:
        logger.exception("Error in run_forge_watchlist_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/alerts')
@login_required
def forge_alerts_api():
    """List persisted Trend Prediction Forge alert events."""
    asset = request.args.get('asset')
    watch_id = request.args.get('watch_id')
    limit = request.args.get('limit', default=50, type=int)
    try:
        return jsonify(list_forge_alerts(asset=asset, watch_id=watch_id, limit=limit))
    except Exception as e:
        logger.exception("Error in forge_alerts_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/forge/alerts', methods=['DELETE'])
@login_required
def clear_forge_alerts_api():
    """Clear persisted Trend Prediction Forge alert events."""
    try:
        return jsonify({'cleared': clear_forge_alerts()})
    except Exception as e:
        logger.exception("Error in clear_forge_alerts_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/wisdom')
@login_required
def get_wisdom_api():
    """Get the current Agent Wisdom Ledger (Lessons and Commandments)."""
    try:
        store = WisdomStore()
        return jsonify({
            'commandments': store.get_commandments(),
            'lessons': store.get_lessons()
        })
    except Exception as e:
        logger.exception("Error in get_wisdom_api")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/analysis/<symbol>')
@login_required
def get_analysis(symbol: str):
    """Get technical price action analysis for a symbol."""
    try:
        data = portfolio_tracker.get_technical_analysis(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.exception("Error in get_analysis")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/whale/<symbol>')
@login_required
def get_whale_analysis(symbol: str):
    """Get whale activity analysis for a symbol."""
    try:
        data = portfolio_tracker.get_whale_analysis(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.exception("Error in get_whale_analysis")
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/<chart_type>/<int:telegram_id>')
@login_required
def get_chart(chart_type: str, telegram_id: int):
    """Get chart data for a specific chart type."""
    try:
        data = portfolio_tracker.get_chart_data(telegram_id, chart_type)
        return jsonify(data)
    except Exception as e:
        logger.exception("Error in get_chart")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
@login_required
def get_trades():
    """Get trade history for a user."""
    telegram_id = request.args.get('telegram_id', type=int)
    limit = request.args.get('limit', 50, type=int)

    if not telegram_id:
        return jsonify({'error': 'Telegram ID required'}), 400

    try:
        trades = portfolio_tracker.get_trade_history(telegram_id, limit=limit)
        return jsonify(trades)
    except Exception as e:
        logger.exception("Error in get_trades")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/chat', methods=['POST'])
@login_required
def agent_chat():
    """Interact with the AI Trading Agent."""
    data = request.json
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
        
    user_message = data['message']
    
    try:
        agent = get_web_agent()
        # Optionally inject user_id context if needed for the agent
        # We can pass the telegram_id so the agent knows who it's trading for
        user_id = data.get('telegram_id')
        if user_id:
            agent.user_id = user_id
            
        response_text = agent.chat(user_message)
        
        return jsonify({
            'response': response_text,
            'status': 'success'
        })
    except Exception as e:
        logger.exception("Error interacting with agent")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return "Internal server error", 500

def accuracy_tracker_loop():
    """Background thread to evaluate AI predictions and trigger retraining."""
    logger.info("Starting accuracy tracker background loop...")
    while True:
        try:
            # Run every hour
            time.sleep(3600)
            logger.info("Running accuracy tracker...")
            ledger = PredictionLedger()
            evaluated = ledger.evaluate_due(
                lambda sym: get_current_prices().get(sym.upper()),
                evaluate_all=False,
            )
            
            if evaluated:
                logger.info(f"Evaluated {len(evaluated)} predictions.")
                symbols = set([r['symbol'] for r in evaluated])
                for symbol in symbols:
                    summary = ledger.summary(symbol=symbol)
                    acc = summary.get('direction_accuracy_pct')
                    if acc is not None and acc < 50.0:
                        logger.warning(f"Accuracy for {symbol} dropped to {acc}%. Triggering emergency retraining...")
                        portfolio_tracker.get_ai_predictions(symbol)
                        logger.info(f"Emergency retraining complete for {symbol}.")
        except Exception as e:
            logger.error(f"Error in accuracy tracker loop: {e}")

def trend_forge_tracker_loop():
    """Background thread to evaluate due Trend Prediction Forge records."""
    interval = int(os.getenv('TREND_FORGE_EVALUATION_INTERVAL_SECONDS', '3600'))
    logger.info("Starting Trend Prediction Forge tracker background loop...")
    while True:
        try:
            time.sleep(interval)
            evaluated = evaluate_due_predictions(evaluate_all=False)
            if evaluated:
                logger.info("Evaluated %s Trend Prediction Forge records.", len(evaluated))
                assets = {record.get('asset') for record in evaluated if record.get('asset')}
                for asset in assets:
                    summary = TrendPredictionLedger().summary(asset=asset)
                    logger.info(
                        "Forge accuracy for %s: direction=%s%% mean_score_error=%s",
                        asset,
                        summary.get('direction_accuracy_pct'),
                        summary.get('mean_score_error'),
                    )
            watch_result = process_due_watchlist(force=False)
            if watch_result["processed"]:
                logger.info(
                    "Processed %s Trend Prediction Forge watches and emitted %s alerts.",
                    len(watch_result["processed"]),
                    len(watch_result["alerts"]),
                )
        except Exception as e:
            logger.error(f"Error in Trend Prediction Forge tracker loop: {e}")

def sentiment_tracker_loop():
    """Background thread to monitor social/news sentiment and alert the risk manager."""
    logger.info("Starting sentiment tracker background loop...")
    from monitoring.sentiment_engine import analyze_sentiment
    from core.agent import Agent
    
    assets = ["BTC", "ETH", "SOL"]
    # Wait a bit before first run
    time.sleep(10)
    while True:
        try:
            logger.info("Running sentiment tracker...")
            for symbol in assets:
                result = analyze_sentiment(symbol)
                agg_score = result.get('aggregate_score', 0)
                
                # Check for extreme hype or FUD
                if agg_score > 0.4 or agg_score < -0.4:
                    logger.warning(f"Extreme sentiment detected for {symbol}: {agg_score}. Alerting Risk Manager.")
                    
                    # Delegate task to Risk Manager
                    agent = Agent(role="risk_manager", sid="sentiment_alert_session")
                    task = (
                        f"High sentiment anomaly detected for {symbol}. "
                        f"Aggregate Score: {agg_score} (News: {result.get('news_sentiment')}, Social: {result.get('social_sentiment')}). "
                        f"Signal: {result.get('signal')}. "
                        f"Please review the situation. Issue a new commandment using the write_strategy or write to the wisdom ledger if necessary."
                    )
                    # We use an internal chat call without full user context
                    # The risk manager can write commandments if it deems necessary
                    agent.chat(task)
            
            # Run every 30 minutes
            time.sleep(1800)
        except Exception as e:
            logger.error(f"Error in sentiment tracker loop: {e}")
            time.sleep(60)

def alert_processor_loop():
    """Background thread to process user-defined smart alerts."""
    logger.info("Starting alert processor background loop...")
    from memory.alerts import AlertStore
    from backend.market_data import get_current_prices
    from monitoring.sentiment_engine import analyze_sentiment
    from tools.wallet_activity import check_wallet_activity
    from core.agent import Agent
    
    while True:
        try:
            store = AlertStore()
            alerts = store.list_alerts()
            if not alerts:
                time.sleep(60)
                continue
                
            prices = get_current_prices()
            
            for alert in alerts:
                if not alert.get("is_active"):
                    continue
                    
                symbol = alert["symbol"]
                alert_type = alert["type"]
                threshold = alert["value"]
                triggered = False
                trigger_val = None
                
                if alert_type == "PRICE_UP" or alert_type == "PRICE_DOWN":
                    current_price = prices.get(symbol)
                    if current_price:
                        if alert_type == "PRICE_UP" and current_price >= threshold:
                            triggered = True
                            trigger_val = current_price
                        elif alert_type == "PRICE_DOWN" and current_price <= threshold:
                            triggered = True
                            trigger_val = current_price
                            
                elif alert_type == "SENTIMENT_SPIKE":
                    sentiment = analyze_sentiment(symbol)
                    score = sentiment.get("aggregate_score", 0)
                    if abs(score) >= threshold:
                        triggered = True
                        trigger_val = score
                elif alert_type == "WALLET_ACTIVITY":
                    wallet_address = alert.get("wallet_address")
                    chain = alert.get("chain", "base")
                    last_seen_tx_hash = alert.get("last_seen_tx_hash")
                    if wallet_address:
                        wallet_activity = check_wallet_activity(
                            wallet_address=wallet_address,
                            chain=chain,
                            last_seen_tx_hash=last_seen_tx_hash,
                        )
                        if wallet_activity.get("has_new_activity"):
                            triggered = True
                            trigger_val = wallet_activity.get("latest_tx_hash")
                    else:
                        logger.warning("Wallet activity alert %s is missing wallet_address", alert["id"])
                        
                if triggered:
                    logger.warning(f"ALERT TRIGGERED: {alert_type} for {symbol} at {trigger_val}")
                    # In a real system, we'd send a Telegram notification here.
                    # For now, we notify the researcher agent to take action.
                    agent = Agent(role="researcher", sid=f"alert_{alert['id']}")
                    if alert_type == "WALLET_ACTIVITY":
                        wallet_address = alert.get("wallet_address", symbol)
                        agent.chat(
                            f"WALLET ALERT TRIGGERED: {wallet_address} on {alert.get('chain', 'base')} showed new on-chain activity."
                            f" Latest tx hash: {trigger_val}. Please provide a brief user-facing summary."
                        )
                        store.update_alert(
                            alert["id"],
                            last_seen_tx_hash=trigger_val,
                            last_triggered=datetime.utcnow().isoformat(),
                        )
                    else:
                        agent.chat(f"SMART ALERT TRIGGERED: {alert_type} for {symbol} hit {trigger_val}. Please provide a brief analysis to the user.")
                    
                    # Deactivate or update last_triggered
                    if alert_type != "WALLET_ACTIVITY":
                        store.update_alert(alert["id"], is_active=False, last_triggered=datetime.utcnow().isoformat())
            
            time.sleep(300) # Check every 5 minutes
        except Exception as e:
            logger.error(f"Error in alert processor loop: {e}")
            time.sleep(60)

def strategy_optimizer_loop():
    """Background thread to periodically optimize strategy parameters."""
    logger.info("Starting strategy optimizer background loop...")
    from tools.optimization_tools import optimize_strategy_parameters
    
    symbols = ["BTC", "ETH", "SOL"]
    while True:
        try:
            # Run every 12 hours
            time.sleep(43200)
            logger.info("Running strategy parameter optimization...")
            for symbol in symbols:
                result = optimize_strategy_parameters(symbol=symbol, days=30)
                logger.info(f"Optimization complete for {symbol}: {result.split('--------------------------------------------------')[1].strip()}")
                
                # In a real system, we'd automatically update the strategy config here.
                # For now, we log the recommendation for the agent to see in logs or next session.
        except Exception as e:
            logger.error(f"Error in strategy optimizer loop: {e}")

def initialize_app():
    """Initialize the application."""
    init_db()
    create_admin_user()
    
    tracker_thread = threading.Thread(target=accuracy_tracker_loop, daemon=True)
    tracker_thread.start()
    
    sentiment_thread = threading.Thread(target=sentiment_tracker_loop, daemon=True)
    sentiment_thread.start()
    
    alert_thread = threading.Thread(target=alert_processor_loop, daemon=True)
    alert_thread.start()

    forge_thread = threading.Thread(target=trend_forge_tracker_loop, daemon=True)
    forge_thread.start()
    
    optimizer_thread = threading.Thread(target=strategy_optimizer_loop, daemon=True)
    optimizer_thread.start()
    
    # from core.orchestrator import autonomous_orchestrator_loop
    # orchestrator_thread = threading.Thread(target=autonomous_orchestrator_loop, daemon=True)
    # orchestrator_thread.start()

def create_admin_user():
    """Create admin user if it doesn't exist."""
    session = SessionLocal()
    try:
        admin = session.query(User).filter_by(telegram_id='admin').first()
        if not admin:
            admin = User(telegram_id='admin', username='admin')
            session.add(admin)
            session.commit()
    finally:
        session.close()

def run_dev_server():
    """Run development server."""
    initialize_app()
    port = int(os.getenv('PORT', 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'True') == 'True'
    )

if __name__ == '__main__':
    run_dev_server()
