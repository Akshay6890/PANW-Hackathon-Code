"""
Reflect AI - Personal Journaling App with AI Insights
Privacy-first design: All data stays local, no cloud uploads.
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Sentiment analysis
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Download NLTK data (only once)
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    logger.info("Downloading NLTK VADER lexicon...")
    nltk.download('vader_lexicon', quiet=True)

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Initialize Flask app with static folder
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Constants
DATA_FILE = "journal_data.json"
MAX_ENTRY_LENGTH = 50000  # Characters
MAX_PHOTOS_PER_ENTRY = 10

# AI Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY:
    logger.info("Groq API configured for AI features")
else:
    logger.warning("No GROQ_API_KEY found. Get one free at https://console.groq.com")


# =============================================================================
# Data Layer
# =============================================================================

def load_data() -> Dict[str, Any]:
    """Load journal data from file with error handling."""
    if not os.path.exists(DATA_FILE):
        return {"entries": {}, "metadata": {"created_at": datetime.now().isoformat()}}
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate structure
        if not isinstance(data, dict):
            logger.warning("Invalid data format, resetting")
            return {"entries": {}, "metadata": {}}
        
        if "entries" not in data:
            data["entries"] = {}
        if "metadata" not in data:
            data["metadata"] = {}
            
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {"entries": {}, "metadata": {}}
    except OSError as e:
        logger.error(f"File read error: {e}")
        return {"entries": {}, "metadata": {}}


def save_data(data: Dict[str, Any]) -> bool:
    """Save journal data atomically with backup."""
    tmp_file = f"{DATA_FILE}.tmp"
    backup_file = f"{DATA_FILE}.bak"
    
    try:
        # Write to temp file first
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Create backup of existing file
        if os.path.exists(DATA_FILE):
            try:
                os.replace(DATA_FILE, backup_file)
            except OSError:
                pass  # Backup is optional
        
        # Atomic rename
        os.replace(tmp_file, DATA_FILE)
        return True
        
    except OSError as e:
        logger.error(f"Save error: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        return False


# =============================================================================
# Sentiment Analysis
# =============================================================================

def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze sentiment of text using VADER.
    Returns compound score (-1 to 1) and mood label.
    """
    if not text or not text.strip():
        return {"compound": 0.0, "mood": "neutral", "scores": {}}
    
    scores = sia.polarity_scores(text)
    compound = scores["compound"]
    
    # Determine mood label with nuanced thresholds
    if compound >= 0.5:
        mood = "very_positive"
    elif compound >= 0.2:
        mood = "positive"
    elif compound > -0.2:
        mood = "neutral"
    elif compound > -0.5:
        mood = "negative"
    else:
        mood = "very_negative"
    
    return {
        "compound": round(compound, 3),
        "mood": mood,
        "scores": {
            "positive": round(scores["pos"], 3),
            "negative": round(scores["neg"], 3),
            "neutral": round(scores["neu"], 3)
        }
    }


def get_mood_emoji(mood: str) -> str:
    """Get emoji for mood label."""
    emojis = {
        "very_positive": "😄",
        "positive": "🙂",
        "neutral": "😐",
        "negative": "😔",
        "very_negative": "😢"
    }
    return emojis.get(mood, "📝")


def get_empathetic_response(mood: str) -> str:
    """Generate empathetic response based on mood."""
    responses = {
        "very_positive": "What a wonderful day! Your positivity shines through your words.",
        "positive": "It sounds like things are going well. Keep nurturing those good moments.",
        "neutral": "Thank you for reflecting today. Every entry helps you understand yourself better.",
        "negative": "It seems like today had some challenges. Remember, it's okay to have difficult days.",
        "very_negative": "I hear that today was tough. Writing about it is a brave step. Be gentle with yourself."
    }
    return responses.get(mood, "Thank you for journaling today.")


# =============================================================================
# Streak & Engagement Tracking
# =============================================================================

def calculate_streak(entries: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate journaling streak and engagement stats.
    """
    if not entries:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "total_entries": 0,
            "this_week": 0,
            "this_month": 0,
            "last_entry_date": None
        }
    
    # Get sorted dates
    dates = []
    for key in entries.keys():
        try:
            dates.append(datetime.strptime(key, "%Y-%m-%d").date())
        except ValueError:
            continue
    
    if not dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "total_entries": 0,
            "this_week": 0,
            "this_month": 0,
            "last_entry_date": None
        }
    
    dates.sort(reverse=True)
    today = datetime.now().date()
    
    # Filter out future dates for streak calculation
    valid_dates = [d for d in dates if d <= today]
    
    # Current streak (consecutive days ending today or yesterday)
    current_streak = 0
    
    if valid_dates:
        # Allow streak to continue if last valid entry was today or yesterday
        if valid_dates[0] == today or valid_dates[0] == today - timedelta(days=1):
            check_date = valid_dates[0]
            for d in valid_dates:
                if d == check_date:
                    current_streak += 1
                    check_date -= timedelta(days=1)
                elif d < check_date:
                    break
    
    # Longest streak (using all dates, including future ones if any)
    longest_streak = 1 if dates else 0
    current_run = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i-1] - timedelta(days=1):
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 1
    
    # This week and month counts
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    this_week = sum(1 for d in dates if d >= week_ago)
    this_month = sum(1 for d in dates if d >= month_start)
    
    return {
        "current_streak": current_streak,
        "longest_streak": max(longest_streak, current_streak),
        "total_entries": len(dates),
        "this_week": this_week,
        "this_month": this_month,
        "last_entry_date": dates[0].isoformat() if dates else None
    }


def get_encouragement_message(streak_data: Dict[str, Any]) -> str:
    """Generate personalized encouragement based on streak."""
    streak = streak_data.get("current_streak", 0)
    total = streak_data.get("total_entries", 0)
    
    if streak == 0:
        if total == 0:
            return "Start your journaling journey today. Every story begins with one page."
        return "Welcome back! Ready to continue your reflection practice?"
    elif streak == 1:
        return "Great start! One day at a time builds lasting habits."
    elif streak < 7:
        return f"{streak} days strong! You're building something meaningful."
    elif streak < 30:
        return f"Amazing {streak}-day streak! Consistency is your superpower."
    elif streak < 100:
        return f"Incredible {streak} days! Your dedication to self-reflection inspires."
    else:
        return f"Legendary {streak}-day streak! You've mastered the art of daily reflection."


# =============================================================================
# AI Integration
# =============================================================================

def generate_text(system_prompt: str, user_prompt: str, max_tokens: int = 256) -> Optional[str]:
    """Generate text using Groq API with error handling."""
    if not GROQ_API_KEY:
        return None
    
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        raise


def extract_themes(text: str) -> List[str]:
    """Extract key themes/topics from text."""
    if not text:
        return []
    
    # Simple keyword-based theme extraction
    theme_keywords = {
        "work": ["work", "job", "office", "meeting", "project", "deadline", "boss", "colleague"],
        "family": ["family", "mom", "dad", "parent", "sister", "brother", "child", "kid"],
        "friends": ["friend", "hangout", "party", "social", "meet", "catch up"],
        "health": ["gym", "workout", "exercise", "run", "walk", "yoga", "sleep", "tired", "energy"],
        "food": ["breakfast", "lunch", "dinner", "eat", "cook", "restaurant", "coffee"],
        "learning": ["study", "learn", "course", "read", "book", "practice", "skill"],
        "emotions": ["happy", "sad", "anxious", "excited", "stressed", "calm", "grateful"],
        "travel": ["travel", "trip", "vacation", "flight", "visit", "explore"],
        "creativity": ["write", "art", "music", "create", "design", "build", "project"]
    }
    
    text_lower = text.lower()
    found_themes = []
    
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            found_themes.append(theme)
    
    return found_themes[:5]  # Return top 5 themes


def extract_activities(text: str) -> List[str]:
    """Extract specific activities mentioned in text for correlation analysis."""
    if not text:
        return []
    
    # Activity patterns to detect
    activity_patterns = {
        "morning_walk": ["morning walk", "walked this morning", "morning stroll", "walked early"],
        "exercise": ["gym", "workout", "exercise", "ran", "jogging", "yoga", "pilates", "weights", "training"],
        "meditation": ["meditat", "mindful", "breathing exercise", "calm app", "headspace"],
        "good_sleep": ["slept well", "great sleep", "rested", "8 hours", "full night", "refreshed"],
        "poor_sleep": ["couldn't sleep", "insomnia", "tired", "exhausted", "didn't sleep", "sleepless"],
        "social_time": ["met friends", "hung out", "dinner with", "called", "video chat", "party", "gathering"],
        "alone_time": ["alone", "by myself", "solo", "quiet time", "solitude"],
        "nature": ["park", "hiking", "beach", "garden", "outdoors", "nature", "trees", "fresh air"],
        "creative_work": ["wrote", "painted", "drew", "created", "designed", "built", "crafted", "composed"],
        "reading": ["read", "book", "article", "reading"],
        "screen_time": ["netflix", "youtube", "scrolling", "social media", "phone", "binge"],
        "healthy_eating": ["salad", "vegetables", "healthy", "cooked", "meal prep", "fruits"],
        "coffee": ["coffee", "caffeine", "espresso", "latte"],
        "alcohol": ["drink", "wine", "beer", "cocktail", "alcohol"],
        "productive_day": ["productive", "accomplished", "got things done", "finished", "completed"],
        "stressed": ["stressed", "overwhelmed", "anxious", "pressure", "deadline"],
        "grateful": ["grateful", "thankful", "blessed", "appreciate", "gratitude"]
    }
    
    text_lower = text.lower()
    found_activities = []
    
    for activity, patterns in activity_patterns.items():
        if any(p in text_lower for p in patterns):
            found_activities.append(activity)
    
    return found_activities


def analyze_activity_mood_correlation(entries: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze correlation between activities and mood scores.
    Returns insights about what activities correlate with better/worse moods.
    """
    if len(entries) < 5:
        return {"correlations": [], "patterns": []}
    
    # Collect activity-mood pairs
    activity_moods = {}  # activity -> list of mood scores
    
    for key, entry in entries.items():
        text = entry.get("text", "")
        sentiment = entry.get("sentiment", {})
        mood_score = sentiment.get("compound", 0)
        
        activities = extract_activities(text)
        for activity in activities:
            if activity not in activity_moods:
                activity_moods[activity] = []
            activity_moods[activity].append(mood_score)
    
    # Calculate average mood for each activity
    correlations = []
    for activity, moods in activity_moods.items():
        if len(moods) >= 2:  # Need at least 2 occurrences
            avg_mood = sum(moods) / len(moods)
            correlations.append({
                "activity": activity,
                "avg_mood": round(avg_mood, 3),
                "occurrences": len(moods),
                "positive": avg_mood > 0.15,
                "negative": avg_mood < -0.15
            })
    
    # Sort by average mood (best correlations first)
    correlations.sort(key=lambda x: x["avg_mood"], reverse=True)
    
    # Generate human-readable patterns
    patterns = []
    
    # Find positive correlations
    positive_activities = [c for c in correlations if c["positive"] and c["occurrences"] >= 2]
    if positive_activities:
        best = positive_activities[0]
        activity_name = best["activity"].replace("_", " ")
        patterns.append({
            "type": "positive_correlation",
            "activity": best["activity"],
            "insight": f"You seem most energized on days involving {activity_name}.",
            "confidence": "high" if best["occurrences"] >= 3 else "moderate"
        })
    
    # Find negative correlations
    negative_activities = [c for c in correlations if c["negative"] and c["occurrences"] >= 2]
    if negative_activities:
        worst = negative_activities[-1] if negative_activities else None
        if worst:
            activity_name = worst["activity"].replace("_", " ")
            patterns.append({
                "type": "negative_correlation", 
                "activity": worst["activity"],
                "insight": f"Days with {activity_name} tend to feel more challenging.",
                "confidence": "high" if worst["occurrences"] >= 3 else "moderate"
            })
    
    return {
        "correlations": correlations[:10],  # Top 10
        "patterns": patterns
    }


def analyze_theme_frequency_by_mood(entries: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze which themes appear more frequently during positive vs negative moods.
    """
    positive_themes = {}
    negative_themes = {}
    
    for key, entry in entries.items():
        sentiment = entry.get("sentiment", {})
        mood_score = sentiment.get("compound", 0)
        themes = entry.get("themes", [])
        
        for theme in themes:
            if mood_score > 0.1:
                positive_themes[theme] = positive_themes.get(theme, 0) + 1
            elif mood_score < -0.1:
                negative_themes[theme] = negative_themes.get(theme, 0) + 1
    
    return {
        "positive_mood_themes": sorted(positive_themes.items(), key=lambda x: x[1], reverse=True)[:5],
        "negative_mood_themes": sorted(negative_themes.items(), key=lambda x: x[1], reverse=True)[:5]
    }


def find_weekly_patterns(entries: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze patterns across days of the week.
    """
    day_moods = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for key, entry in entries.items():
        try:
            date = datetime.strptime(key, "%Y-%m-%d")
            day_of_week = date.weekday()
            mood_score = entry.get("sentiment", {}).get("compound", 0)
            day_moods[day_of_week].append(mood_score)
        except ValueError:
            continue
    
    # Calculate average mood per day
    day_averages = []
    for day, moods in day_moods.items():
        if len(moods) >= 2:
            avg = sum(moods) / len(moods)
            day_averages.append({
                "day": day_names[day],
                "day_num": day,
                "avg_mood": round(avg, 3),
                "entry_count": len(moods)
            })
    
    if not day_averages:
        return []
    
    # Sort by mood
    day_averages.sort(key=lambda x: x["avg_mood"], reverse=True)
    
    patterns = []
    if len(day_averages) >= 2:
        best_day = day_averages[0]
        worst_day = day_averages[-1]
        
        if best_day["avg_mood"] > worst_day["avg_mood"] + 0.2:
            patterns.append({
                "type": "day_pattern",
                "insight": f"{best_day['day']}s tend to be your best days, while {worst_day['day']}s are more challenging.",
                "best_day": best_day["day"],
                "challenging_day": worst_day["day"]
            })
    
    return patterns


# =============================================================================
# Request Validation
# =============================================================================

def validate_date_key(date_key: str) -> bool:
    """Validate date key format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_key, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_entry_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate entry data."""
    if not isinstance(data, dict):
        return False, "Invalid data format"
    
    text = data.get("text", "")
    if not isinstance(text, str):
        return False, "Text must be a string"
    
    if len(text) > MAX_ENTRY_LENGTH:
        return False, f"Text exceeds maximum length of {MAX_ENTRY_LENGTH} characters"
    
    photos = data.get("photos", [])
    if not isinstance(photos, list):
        return False, "Photos must be a list"
    
    if len(photos) > MAX_PHOTOS_PER_ENTRY:
        return False, f"Maximum {MAX_PHOTOS_PER_ENTRY} photos allowed"
    
    return True, ""


def handle_errors(f):
    """Decorator for consistent error handling."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}")
            return jsonify({"error": "An unexpected error occurred"}), 500
    return wrapper


# =============================================================================
# API Routes
# =============================================================================

@app.route("/")
def index():
    """Serve the main application."""
    return send_file("index.html")


@app.route("/api/entries", methods=["GET"])
@handle_errors
def get_entries():
    """Get all entries with sentiment data."""
    data = load_data()
    return jsonify(data)


@app.route("/api/entries/<date_key>", methods=["GET"])
@handle_errors
def get_entry(date_key: str):
    """Get a specific entry by date."""
    if not validate_date_key(date_key):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    data = load_data()
    entry = data["entries"].get(date_key)
    
    if entry:
        return jsonify(entry)
    return jsonify({"error": "Entry not found"}), 404


@app.route("/api/entries/<date_key>", methods=["POST", "PUT"])
@handle_errors
def save_entry(date_key: str):
    """Save or update an entry with automatic sentiment analysis."""
    if not validate_date_key(date_key):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    body = request.get_json()
    if not body:
        return jsonify({"error": "No data provided"}), 400
    
    valid, error_msg = validate_entry_data(body)
    if not valid:
        return jsonify({"error": error_msg}), 400
    
    data = load_data()
    text = body.get("text", "").strip()
    photos = body.get("photos", [])
    tags = body.get("tags", [])
    
    # Validate tags
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip()[:30] for t in tags if t][:10]  # Max 10 tags, 30 chars each
    
    # Delete entry if empty
    if not text and not photos:
        if date_key in data["entries"]:
            del data["entries"][date_key]
            save_data(data)
        return jsonify({"deleted": True})
    
    # Analyze sentiment
    sentiment = analyze_sentiment(text)
    themes = extract_themes(text)
    
    # Create entry with metadata
    entry = {
        "text": text,
        "photos": photos,
        "tags": tags,
        "sentiment": sentiment,
        "themes": themes,
        "word_count": len(text.split()),
        "updatedAt": datetime.now().isoformat()
    }
    
    data["entries"][date_key] = entry
    
    if not save_data(data):
        return jsonify({"error": "Failed to save entry"}), 500
    
    # Return with empathetic response
    response = {
        "saved": True,
        "entry": entry,
        "encouragement": get_empathetic_response(sentiment["mood"])
    }
    
    return jsonify(response)


@app.route("/api/entries/<date_key>", methods=["DELETE"])
@handle_errors
def delete_entry(date_key: str):
    """Delete an entry."""
    if not validate_date_key(date_key):
        return jsonify({"error": "Invalid date format"}), 400
    
    data = load_data()
    if date_key in data["entries"]:
        del data["entries"][date_key]
        save_data(data)
        return jsonify({"deleted": True})
    return jsonify({"error": "Entry not found"}), 404


# =============================================================================
# Navigation Routes
# =============================================================================

@app.route("/api/years", methods=["GET"])
@handle_errors
def get_years():
    """Get list of years with entries."""
    data = load_data()
    years = set()
    
    for key in data["entries"].keys():
        try:
            years.add(int(key.split("-")[0]))
        except (ValueError, IndexError):
            continue
    
    return jsonify(sorted(years, reverse=True))


@app.route("/api/years/<int:year>/months", methods=["GET"])
@handle_errors
def get_months(year: int):
    """Get months with entries for a given year."""
    data = load_data()
    prefix = f"{year}-"
    months = set()
    
    for key in data["entries"].keys():
        if key.startswith(prefix):
            try:
                months.add(int(key.split("-")[1]))
            except (ValueError, IndexError):
                continue
    
    return jsonify(sorted(months))


@app.route("/api/years/<int:year>/months/<int:month>/days", methods=["GET"])
@handle_errors
def get_days(year: int, month: int):
    """Get days with entries for a given month."""
    data = load_data()
    prefix = f"{year}-{month:02d}-"
    days = []
    
    for key, entry in data["entries"].items():
        if key.startswith(prefix):
            try:
                day = int(key.split("-")[2])
                text = entry.get("text", "")
                sentiment = entry.get("sentiment", {})
                
                days.append({
                    "day": day,
                    "key": key,
                    "preview": (text[:50] + "...") if len(text) > 50 else text,
                    "hasPhotos": len(entry.get("photos", [])) > 0,
                    "mood": sentiment.get("mood", "neutral"),
                    "moodEmoji": get_mood_emoji(sentiment.get("mood", "neutral"))
                })
            except (ValueError, IndexError):
                continue
    
    return jsonify(sorted(days, key=lambda x: x["day"]))


# =============================================================================
# Analytics & Insights Routes
# =============================================================================

@app.route("/api/greeting", methods=["GET"])
@handle_errors
def get_greeting():
    """Generate a personalized greeting based on journal data."""
    data = load_data()
    entries = data.get("entries", {})
    
    today = datetime.now()
    hour = today.hour
    time_greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    today_key = today.strftime("%Y-%m-%d")
    
    # Check for recent entries
    recent_entries = []
    for i in range(7):
        date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if date_key in entries:
            recent_entries.append({
                "date": date_key,
                "mood": entries[date_key].get("sentiment", {}).get("mood", "neutral"),
                "themes": entries[date_key].get("themes", []),
                "preview": entries[date_key].get("text", "")[:100]
            })
    
    # Calculate streak
    streak_data = calculate_streak(entries)
    streak = streak_data.get("current", 0)
    
    # If no entries, return motivational message
    if not entries:
        motivational_quotes = [
            "Every great journey begins with a single step. Start your journaling adventure today!",
            "Your thoughts matter. Take a moment to capture them.",
            "The best time to start journaling was yesterday. The second best time is now.",
            "Writing is thinking on paper. Begin your reflection journey today.",
            "A journal is a friend who listens without judgment. Say hello!"
        ]
        import random
        return jsonify({
            "greeting": time_greeting,
            "message": random.choice(motivational_quotes),
            "has_entries": False,
            "streak": 0
        })
    
    # If no Groq API, return simple personalized message
    if not GROQ_API_KEY:
        if today_key in entries:
            message = f"Welcome back! You've already journaled today. Keep the momentum going!"
        elif streak > 0:
            message = f"You're on a {streak}-day streak! Don't break it - write today."
        else:
            message = "Ready to reflect? Your journal awaits."
        
        return jsonify({
            "greeting": time_greeting,
            "message": message,
            "has_entries": True,
            "streak": streak,
            "total_entries": len(entries)
        })
    
    # Build context for AI
    context_parts = []
    context_parts.append(f"Total journal entries: {len(entries)}")
    context_parts.append(f"Current streak: {streak} days")
    context_parts.append(f"Already journaled today: {'yes' if today_key in entries else 'no'}")
    
    if recent_entries:
        moods = [e["mood"] for e in recent_entries]
        mood_summary = "mostly positive" if moods.count("positive") + moods.count("very_positive") > len(moods)/2 else \
                       "mixed" if moods.count("neutral") > len(moods)/2 else "reflective"
        context_parts.append(f"Recent mood: {mood_summary}")
        
        # Get common themes
        all_themes = []
        for e in recent_entries:
            all_themes.extend(e.get("themes", []))
        if all_themes:
            from collections import Counter
            top_themes = [t for t, _ in Counter(all_themes).most_common(3)]
            context_parts.append(f"Recent themes: {', '.join(top_themes)}")
    
    system_prompt = """You are a warm, encouraging journaling companion greeting the user.
Generate a brief, personalized greeting (1-2 sentences max) based on their journaling context.

Guidelines:
- Be warm but not overly enthusiastic
- If they have a streak, acknowledge it naturally
- If they already journaled today, congratulate them subtly
- If they haven't journaled in a while, gently encourage without guilt
- Reference their recent themes or moods if relevant
- Keep it under 30 words
- Don't use exclamation marks excessively
- Sound natural, like a supportive friend"""

    user_prompt = f"""Time: {time_greeting}
Context:
{chr(10).join(context_parts)}

Generate a brief personalized greeting."""

    try:
        message = generate_text(system_prompt, user_prompt, max_tokens=60)
        return jsonify({
            "greeting": time_greeting,
            "message": message,
            "has_entries": True,
            "streak": streak,
            "total_entries": len(entries),
            "ai_generated": True
        })
    except Exception as e:
        logger.error(f"Greeting AI error: {e}")
        return jsonify({
            "greeting": time_greeting,
            "message": f"Welcome back! You have {len(entries)} entries in your journal.",
            "has_entries": True,
            "streak": streak,
            "total_entries": len(entries),
            "ai_generated": False
        })


@app.route("/api/stats", methods=["GET"])
@handle_errors
def get_stats():
    """Get journaling statistics and engagement data."""
    data = load_data()
    entries = data.get("entries", {})
    
    streak_data = calculate_streak(entries)
    encouragement = get_encouragement_message(streak_data)
    
    # Calculate mood distribution
    mood_counts = {"very_positive": 0, "positive": 0, "neutral": 0, "negative": 0, "very_negative": 0}
    total_words = 0
    
    for entry in entries.values():
        mood = entry.get("sentiment", {}).get("mood", "neutral")
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
        total_words += entry.get("word_count", 0)
    
    # Build last 7 days chain for visual display
    today = datetime.now().date()
    week_chain = []
    for i in range(6, -1, -1):  # 6 days ago to today
        day = today - timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        week_chain.append({
            "date": day_key,
            "day": day.strftime("%a")[0],  # M, T, W, etc.
            "has_entry": day_key in entries,
            "is_today": i == 0
        })
    
    # Check if journaled today
    today_key = today.strftime("%Y-%m-%d")
    journaled_today = today_key in entries
    
    # Calculate hours remaining in day
    now = datetime.now()
    midnight = datetime.combine(today + timedelta(days=1), datetime.min.time())
    hours_remaining = round((midnight - now).total_seconds() / 3600, 1)
    
    # Streak status and urgency
    current_streak = streak_data.get("current_streak", 0)
    streak_status = "safe"  # safe, at_risk, broken
    if not journaled_today:
        if current_streak > 0:
            if hours_remaining < 6:
                streak_status = "at_risk"
            elif hours_remaining < 12:
                streak_status = "reminder"
        else:
            streak_status = "start"
    
    # Calculate badges/milestones
    badges = []
    milestone_days = [7, 14, 30, 60, 100, 365]
    for milestone in milestone_days:
        badges.append({
            "days": milestone,
            "achieved": current_streak >= milestone or streak_data.get("longest_streak", 0) >= milestone,
            "label": f"{milestone} Day{'s' if milestone > 1 else ''}"
        })
    
    # Next milestone
    next_milestone = None
    for milestone in milestone_days:
        if current_streak < milestone:
            next_milestone = {
                "days": milestone,
                "remaining": milestone - current_streak,
                "progress": round(current_streak / milestone * 100)
            }
            break
    
    # Weekly goal (default: 5 days)
    weekly_goal = 5
    this_week = streak_data.get("this_week", 0)
    weekly_progress = round(this_week / weekly_goal * 100)
    
    return jsonify({
        "streak": streak_data,
        "encouragement": encouragement,
        "mood_distribution": mood_counts,
        "total_words": total_words,
        "average_words": round(total_words / len(entries)) if entries else 0,
        # New engagement data
        "week_chain": week_chain,
        "journaled_today": journaled_today,
        "hours_remaining": hours_remaining,
        "streak_status": streak_status,
        "badges": badges,
        "next_milestone": next_milestone,
        "weekly_goal": {
            "target": weekly_goal,
            "current": this_week,
            "progress": min(weekly_progress, 100)
        }
    })


@app.route("/api/insights/charts", methods=["GET"])
@handle_errors
def get_chart_data():
    """Get data formatted for chart visualizations. Accepts optional year/month params."""
    data = load_data()
    all_entries = data.get("entries", {})
    
    # Get optional month filter from query params
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    # Filter entries by month if specified
    if year and month:
        entries = {}
        month_prefix = f"{year}-{str(month).zfill(2)}"
        for key, entry in all_entries.items():
            if key.startswith(month_prefix):
                entries[key] = entry
        month_name = datetime(year, month, 1).strftime("%B %Y")
    else:
        entries = all_entries
        month_name = "All Time"
    
    if not entries:
        return jsonify({
            "has_data": False,
            "month_name": month_name,
            "message": f"No entries for {month_name}. Start journaling to see insights!"
        })
    
    # Get the number of days in the selected month
    if year and month:
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        
        # 1. Mood trend - all days in the month
        mood_trend = []
        for day in range(1, days_in_month + 1):
            date_key = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
            date_label = str(day)
            if date_key in entries:
                score = entries[date_key].get("sentiment", {}).get("compound", 0)
                mood_trend.append({"date": date_label, "score": round(score, 2), "has_entry": True})
            else:
                mood_trend.append({"date": date_label, "score": None, "has_entry": False})
    else:
        # For all-time, show last 31 days
        today = datetime.now().date()
        mood_trend = []
        for i in range(30, -1, -1):
            date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            date_label = (today - timedelta(days=i)).strftime("%b %d")
            if date_key in all_entries:
                score = all_entries[date_key].get("sentiment", {}).get("compound", 0)
                mood_trend.append({"date": date_label, "score": round(score, 2), "has_entry": True})
            else:
                mood_trend.append({"date": date_label, "score": None, "has_entry": False})
    
    # 2. Day of week distribution (for filtered entries)
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    day_counts = {d: 0 for d in day_names}
    day_moods = {d: [] for d in day_names}
    
    for date_key, entry in entries.items():
        try:
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            day_idx = (date_obj.weekday() + 1) % 7
            day_name = day_names[day_idx]
            day_counts[day_name] += 1
            mood_score = entry.get("sentiment", {}).get("compound", 0)
            day_moods[day_name].append(mood_score)
        except:
            pass
    
    day_avg_moods = {}
    for day, moods in day_moods.items():
        day_avg_moods[day] = round(sum(moods) / len(moods), 2) if moods else 0
    
    # 3. Theme frequency (for filtered entries)
    theme_counts = {}
    for entry in entries.values():
        for theme in entry.get("themes", []):
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    
    top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    
    # 4. Mood distribution (for filtered entries)
    mood_distribution = {"very_positive": 0, "positive": 0, "neutral": 0, "negative": 0, "very_negative": 0}
    for entry in entries.values():
        mood = entry.get("sentiment", {}).get("mood", "neutral")
        if mood in mood_distribution:
            mood_distribution[mood] += 1
    
    # 5. Weekly entries within the month (or last 8 weeks for all-time)
    weekly_entries = []
    if year and month:
        # Show weeks within the month
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        week_num = 1
        for week_start_day in range(1, days_in_month + 1, 7):
            week_end_day = min(week_start_day + 6, days_in_month)
            week_label = f"Week {week_num}"
            count = 0
            for day in range(week_start_day, week_end_day + 1):
                date_key = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
                if date_key in entries:
                    count += 1
            weekly_entries.append({"week": week_label, "count": count})
            week_num += 1
    else:
        today = datetime.now().date()
        for week in range(7, -1, -1):
            week_start = today - timedelta(days=today.weekday() + 7 * week)
            week_label = week_start.strftime("%b %d")
            count = 0
            for i in range(7):
                date_key = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
                if date_key in all_entries:
                    count += 1
            weekly_entries.append({"week": week_label, "count": count})
    
    # 6. Word count by week
    weekly_words = []
    if year and month:
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        week_num = 1
        for week_start_day in range(1, days_in_month + 1, 7):
            week_end_day = min(week_start_day + 6, days_in_month)
            week_label = f"Week {week_num}"
            words = []
            for day in range(week_start_day, week_end_day + 1):
                date_key = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
                if date_key in entries:
                    words.append(entries[date_key].get("word_count", 0))
            avg = round(sum(words) / len(words)) if words else 0
            weekly_words.append({"week": week_label, "avg_words": avg})
            week_num += 1
    else:
        today = datetime.now().date()
        for week in range(7, -1, -1):
            week_start = today - timedelta(days=today.weekday() + 7 * week)
            week_label = week_start.strftime("%b %d")
            words = []
            for i in range(7):
                date_key = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
                if date_key in all_entries:
                    words.append(all_entries[date_key].get("word_count", 0))
            avg = round(sum(words) / len(words)) if words else 0
            weekly_words.append({"week": week_label, "avg_words": avg})
    
    # Generate meaningful user-focused insights
    insights_text = []
    
    # Mood trend insight
    if len(mood_trend) > 1:
        recent_moods = [m["score"] for m in mood_trend[-7:] if m["score"] is not None]
        if recent_moods:
            trend_direction = "improving" if recent_moods[-1] > recent_moods[0] else "shifting" if abs(recent_moods[-1] - recent_moods[0]) > 0.1 else "steady"
            insights_text.append(f"Your mood has been {trend_direction} recently.")
    
    # Best days of week
    best_day = max(day_avg_moods.items(), key=lambda x: x[1])[0] if any(day_avg_moods.values()) else None
    if best_day:
        insights_text.append(f"You tend to feel best on {best_day}s.")
    
    # Theme insights
    if top_themes:
        theme_list = ", ".join([t[0].title() for t in top_themes[:3]])
        insights_text.append(f"You've been reflecting on: {theme_list}.")
    
    return jsonify({
        "has_data": True,
        "month_name": month_name,
        "mood_trend": mood_trend,
        "day_distribution": {
            "days": day_names,
            "counts": [day_counts[d] for d in day_names],
            "avg_moods": [day_avg_moods[d] for d in day_names]
        },
        "themes": {
            "labels": [t[0].title() for t in top_themes],
            "counts": [t[1] for t in top_themes]
        },
        "mood_distribution": mood_distribution,
        "weekly_entries": weekly_entries,
        "weekly_words": weekly_words,
        "total_entries": len(entries),
        "insights": insights_text,
        "best_day": best_day
    })


@app.route("/api/insights", methods=["GET"])
@handle_errors
def get_insights():
    """Get AI-powered insights about journaling patterns."""
    data = load_data()
    entries = data.get("entries", {})
    
    if len(entries) < 3:
        return jsonify({
            "insights": [],
            "message": "Write at least 3 entries to unlock personalized insights."
        })
    
    # Gather recent entries for analysis
    sorted_keys = sorted(entries.keys(), reverse=True)[:14]  # Last 2 weeks
    recent_entries = {k: entries[k] for k in sorted_keys}
    
    # Analyze patterns
    moods = []
    themes_count = {}
    total_sentiment = 0
    
    for key in sorted_keys:
        entry = entries[key]
        sentiment = entry.get("sentiment", {})
        moods.append(sentiment.get("compound", 0))
        total_sentiment += sentiment.get("compound", 0)
        
        for theme in entry.get("themes", []):
            themes_count[theme] = themes_count.get(theme, 0) + 1
    
    # Calculate mood trend
    if len(moods) >= 2:
        first_half_avg = sum(moods[len(moods)//2:]) / (len(moods) - len(moods)//2)
        second_half_avg = sum(moods[:len(moods)//2]) / (len(moods)//2) if len(moods)//2 > 0 else 0
        mood_trend = "improving" if second_half_avg > first_half_avg + 0.1 else \
                     "declining" if second_half_avg < first_half_avg - 0.1 else "stable"
    else:
        mood_trend = "stable"
    
    # Top themes
    top_themes = sorted(themes_count.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Average mood
    avg_mood = total_sentiment / len(sorted_keys) if sorted_keys else 0
    avg_mood_label = "positive" if avg_mood > 0.2 else "negative" if avg_mood < -0.2 else "balanced"
    
    insights = []
    
    # Activity-mood correlations (the "connecting dots" feature)
    activity_analysis = analyze_activity_mood_correlation(entries)
    for pattern in activity_analysis.get("patterns", []):
        insights.append({
            "type": "activity_correlation",
            "title": "Activity Pattern",
            "description": pattern["insight"],
            "emoji": "🔗",
            "confidence": pattern.get("confidence", "moderate")
        })
    
    # Day of week patterns
    weekly_patterns = find_weekly_patterns(entries)
    for pattern in weekly_patterns:
        insights.append({
            "type": "weekly_pattern",
            "title": "Weekly Rhythm",
            "description": pattern["insight"],
            "emoji": "📅"
        })
    
    # Mood trend insight
    insights.append({
        "type": "mood_trend",
        "title": "Mood Trend",
        "description": f"Your overall mood has been {mood_trend} over the past entries.",
        "emoji": "📈" if mood_trend == "improving" else "📉" if mood_trend == "declining" else "➡️"
    })
    
    # Theme insight
    if top_themes:
        theme_names = [t[0] for t in top_themes]
        insights.append({
            "type": "themes",
            "title": "Common Themes",
            "description": f"You write most about: {', '.join(theme_names)}",
            "emoji": "🎯"
        })
    
    # Theme-mood correlation
    theme_mood_analysis = analyze_theme_frequency_by_mood(entries)
    positive_themes = theme_mood_analysis.get("positive_mood_themes", [])
    if positive_themes and len(positive_themes) >= 2:
        theme_names = [t[0] for t in positive_themes[:2]]
        insights.append({
            "type": "theme_mood",
            "title": "Positive Triggers",
            "description": f"Writing about {' and '.join(theme_names)} often coincides with better moods.",
            "emoji": "✨"
        })
    
    return jsonify({
        "insights": insights,
        "mood_trend": mood_trend,
        "average_sentiment": round(avg_mood, 2),
        "top_themes": top_themes,
        "activity_correlations": activity_analysis.get("correlations", [])[:5],
        "entries_analyzed": len(sorted_keys)
    })


@app.route("/api/insights/weekly", methods=["GET"])
@handle_errors
def get_weekly_insights():
    """Get AI-generated weekly summary with pattern connections."""
    data = load_data()
    entries = data.get("entries", {})
    
    # Get last 7 days of entries
    today = datetime.now().date()
    week_entries = []
    week_entries_full = {}
    
    for i in range(7):
        date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if date_key in entries:
            entry = entries[date_key]
            week_entries.append({
                "date": date_key,
                "text": entry.get("text", "")[:300],
                "mood": entry.get("sentiment", {}).get("mood", "neutral"),
                "mood_score": entry.get("sentiment", {}).get("compound", 0),
                "themes": entry.get("themes", []),
                "activities": extract_activities(entry.get("text", ""))
            })
            week_entries_full[date_key] = entry
    
    if not week_entries:
        return jsonify({
            "summary": None,
            "message": "No entries this week. Start journaling to get weekly insights!"
        })
    
    # Analyze patterns for this week
    activity_analysis = analyze_activity_mood_correlation(week_entries_full)
    weekly_patterns = find_weekly_patterns(entries)  # Use all entries for day patterns
    
    # Build pattern insights
    pattern_insights = []
    
    # Activity correlations
    for pattern in activity_analysis.get("patterns", []):
        pattern_insights.append(pattern["insight"])
    
    # Check for specific interesting correlations
    correlations = activity_analysis.get("correlations", [])
    for corr in correlations[:3]:
        if corr["occurrences"] >= 2:
            activity_name = corr["activity"].replace("_", " ")
            if corr["positive"]:
                pattern_insights.append(
                    f"You mentioned {activity_name} {corr['occurrences']} times this week, "
                    f"and those entries had notably positive energy."
                )
            elif corr["negative"]:
                pattern_insights.append(
                    f"Entries mentioning {activity_name} tended to have a more reflective tone."
                )
    
    # Theme patterns
    theme_mood = analyze_theme_frequency_by_mood(week_entries_full)
    positive_themes = theme_mood.get("positive_mood_themes", [])
    if positive_themes:
        top_positive = positive_themes[0][0]
        pattern_insights.append(
            f"Writing about {top_positive} seemed to coincide with better moods."
        )
    
    if not GROQ_API_KEY:
        # Return detailed insights without AI
        moods = [e["mood"] for e in week_entries]
        avg_mood = sum(e["mood_score"] for e in week_entries) / len(week_entries)
        
        # Build non-AI summary
        mood_desc = "positive" if avg_mood > 0.1 else "challenging" if avg_mood < -0.1 else "balanced"
        basic_summary = f"You wrote {len(week_entries)} entries this week with a {mood_desc} overall tone."
        
        if pattern_insights:
            basic_summary += " " + pattern_insights[0]
        
        return jsonify({
            "summary": basic_summary,
            "entries_count": len(week_entries),
            "predominant_mood": max(set(moods), key=moods.count),
            "pattern_insights": pattern_insights[:3],
            "ai_available": False
        })
    
    # Build context for AI with pattern data
    entries_text = "\n".join([
        f"- {e['date']} (mood: {e['mood']}): {e['text']}" 
        for e in week_entries
    ])
    
    pattern_context = ""
    if pattern_insights:
        pattern_context = "\n\nDetected patterns:\n" + "\n".join(f"- {p}" for p in pattern_insights[:3])
    
    system_prompt = """You are a warm, insightful journaling companion. Analyze the user's journal entries 
and the detected patterns to provide a personalized weekly reflection.

Your response should:
1. Start with a 2-3 sentence summary of their emotional journey this week
2. Highlight 1-2 specific patterns connecting their activities to their moods 
   (e.g., "You mentioned feeling most energized on days you had a morning walk")
3. Note any themes that appeared during positive moments
4. End with one gentle, personalized suggestion based on what seems to work for them

Be warm, specific, and observant. Reference actual details from their entries.
Avoid generic advice. Keep total response under 200 words.
Write in second person ("You...") and be encouraging but not overly effusive."""

    user_prompt = f"""Journal entries from this week:
{entries_text}
{pattern_context}

Please provide a personalized weekly reflection that connects the dots between their activities, 
themes, and emotional patterns."""

    try:
        summary = generate_text(system_prompt, user_prompt, max_tokens=300)
        return jsonify({
            "summary": summary,
            "entries_count": len(week_entries),
            "pattern_insights": pattern_insights[:3],
            "activity_correlations": correlations[:5],
            "ai_available": True
        })
    except Exception as e:
        logger.error(f"Weekly insights AI error: {e}")
        
        # Fallback with patterns
        fallback = f"You wrote {len(week_entries)} entries this week."
        if pattern_insights:
            fallback += " " + pattern_insights[0]
        
        return jsonify({
            "summary": fallback,
            "entries_count": len(week_entries),
            "pattern_insights": pattern_insights[:3],
            "ai_available": False,
            "error": str(e)
        })


@app.route("/api/insights/monthly", methods=["GET"])
@handle_errors
def get_monthly_insights():
    """Get AI-generated monthly summary with deep pattern analysis."""
    data = load_data()
    entries = data.get("entries", {})
    
    # Get last 30 days of entries
    today = datetime.now().date()
    month_entries = {}
    
    for i in range(30):
        date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if date_key in entries:
            month_entries[date_key] = entries[date_key]
    
    if len(month_entries) < 5:
        return jsonify({
            "summary": None,
            "message": "Write at least 5 entries this month to unlock monthly insights."
        })
    
    # Deep pattern analysis
    activity_analysis = analyze_activity_mood_correlation(month_entries)
    theme_mood = analyze_theme_frequency_by_mood(month_entries)
    weekly_patterns = find_weekly_patterns(month_entries)
    
    # Calculate progress metrics
    sorted_keys = sorted(month_entries.keys())
    first_half = sorted_keys[:len(sorted_keys)//2]
    second_half = sorted_keys[len(sorted_keys)//2:]
    
    first_avg = sum(month_entries[k].get("sentiment", {}).get("compound", 0) for k in first_half) / len(first_half) if first_half else 0
    second_avg = sum(month_entries[k].get("sentiment", {}).get("compound", 0) for k in second_half) / len(second_half) if second_half else 0
    
    mood_trajectory = "improving" if second_avg > first_avg + 0.1 else \
                      "needs attention" if second_avg < first_avg - 0.1 else "steady"
    
    # Build comprehensive insights
    insights = []
    
    # Activity insights
    for pattern in activity_analysis.get("patterns", []):
        insights.append({
            "type": "activity",
            "text": pattern["insight"],
            "emoji": "🔗"
        })
    
    # Best activities
    positive_activities = [c for c in activity_analysis.get("correlations", []) 
                         if c["positive"] and c["occurrences"] >= 3]
    if positive_activities:
        activities = [a["activity"].replace("_", " ") for a in positive_activities[:2]]
        insights.append({
            "type": "positive_triggers",
            "text": f"Activities that boosted your mood: {', '.join(activities)}",
            "emoji": "⚡"
        })
    
    # Theme patterns
    positive_themes = theme_mood.get("positive_mood_themes", [])
    if positive_themes:
        themes = [t[0] for t in positive_themes[:2]]
        insights.append({
            "type": "themes",
            "text": f"Writing about {' and '.join(themes)} often coincided with positive entries.",
            "emoji": "✨"
        })
    
    # Weekly rhythm
    for pattern in weekly_patterns:
        insights.append({
            "type": "weekly",
            "text": pattern["insight"],
            "emoji": "📅"
        })
    
    if not GROQ_API_KEY:
        return jsonify({
            "summary": f"You wrote {len(month_entries)} entries this month. Your mood has been {mood_trajectory}.",
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "insights": insights,
            "ai_available": False
        })
    
    # Build AI prompt with rich context
    entries_summary = []
    for key in sorted(month_entries.keys(), reverse=True)[:10]:
        entry = month_entries[key]
        mood = entry.get("sentiment", {}).get("mood", "neutral")
        preview = entry.get("text", "")[:100]
        activities = extract_activities(entry.get("text", ""))
        entries_summary.append(f"- {key} ({mood}): {preview}... [activities: {', '.join(activities) or 'none noted'}]")
    
    insights_text = "\n".join([f"- {i['text']}" for i in insights])
    
    system_prompt = """You are a thoughtful journaling companion providing a monthly reflection.

Create a warm, insightful summary that:
1. Acknowledges their journaling consistency
2. Identifies 2-3 specific patterns connecting activities to emotional states
   (e.g., "You mentioned feeling most energized on days you had a morning walk. 
   You also wrote about creative ideas more frequently during those weeks.")
3. Notes any positive trends or growth areas
4. Provides one personalized suggestion based on what seems to work for them

Be specific and reference actual patterns. Avoid generic advice.
Keep response under 250 words. Write warmly but not effusively."""

    user_prompt = f"""Monthly journaling data:
- Total entries: {len(month_entries)}
- Mood trajectory: {mood_trajectory}

Recent entries sample:
{chr(10).join(entries_summary)}

Detected patterns:
{insights_text}

Please provide a thoughtful monthly reflection that connects these dots and helps 
the user understand what activities and themes contribute to their wellbeing."""

    try:
        summary = generate_text(system_prompt, user_prompt, max_tokens=350)
        return jsonify({
            "summary": summary,
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "insights": insights,
            "activity_correlations": activity_analysis.get("correlations", [])[:5],
            "ai_available": True
        })
    except Exception as e:
        logger.error(f"Monthly insights AI error: {e}")
        return jsonify({
            "summary": f"You wrote {len(month_entries)} entries this month with a {mood_trajectory} emotional trend.",
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "insights": insights,
            "ai_available": False,
            "error": str(e)
        })


@app.route("/api/insights/summary", methods=["GET"])
@handle_errors
def get_month_summary():
    """Get AI-generated summary for a specific month."""
    data = load_data()
    all_entries = data.get("entries", {})
    
    # Get month filter from query params
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    if not year or not month:
        return jsonify({"error": "Year and month parameters required"}), 400
    
    # Filter entries for the specific month
    month_prefix = f"{year}-{str(month).zfill(2)}"
    month_entries = {k: v for k, v in all_entries.items() if k.startswith(month_prefix)}
    
    month_name = datetime(year, month, 1).strftime("%B %Y")
    
    if len(month_entries) < 3:
        return jsonify({
            "summary": None,
            "month_name": month_name,
            "entries_count": len(month_entries),
            "message": f"Write at least 3 entries in {month_name} to unlock AI insights."
        })
    
    # Analyze patterns for this month
    activity_analysis = analyze_activity_mood_correlation(month_entries)
    theme_mood = analyze_theme_frequency_by_mood(month_entries)
    
    # Calculate mood metrics
    sorted_keys = sorted(month_entries.keys())
    mood_scores = [month_entries[k].get("sentiment", {}).get("compound", 0) for k in sorted_keys]
    avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 0
    
    # Mood trend within the month
    if len(mood_scores) >= 4:
        first_half = mood_scores[:len(mood_scores)//2]
        second_half = mood_scores[len(mood_scores)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        mood_trajectory = "improving" if second_avg > first_avg + 0.1 else \
                          "declining" if second_avg < first_avg - 0.1 else "steady"
    else:
        mood_trajectory = "steady"
    
    # Most common themes
    theme_counts = {}
    for entry in month_entries.values():
        for theme in entry.get("themes", []):
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Best and challenging days
    best_day = max(month_entries.items(), key=lambda x: x[1].get("sentiment", {}).get("compound", 0))
    challenging_day = min(month_entries.items(), key=lambda x: x[1].get("sentiment", {}).get("compound", 0))
    
    # Build insights list
    insights = []
    
    for pattern in activity_analysis.get("patterns", [])[:3]:
        insights.append(pattern["insight"])
    
    positive_themes = theme_mood.get("positive_mood_themes", [])
    if positive_themes:
        themes = [t[0] for t in positive_themes[:2]]
        insights.append(f"Writing about {' and '.join(themes)} often coincided with positive moods.")
    
    if not GROQ_API_KEY:
        fallback_summary = f"In {month_name}, you wrote {len(month_entries)} journal entries. "
        fallback_summary += f"Your overall mood was {'positive' if avg_mood > 0.2 else 'reflective' if avg_mood < -0.2 else 'balanced'}. "
        if top_themes:
            fallback_summary += f"Common themes included {', '.join([t[0] for t in top_themes[:3]])}."
        return jsonify({
            "summary": fallback_summary,
            "month_name": month_name,
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "avg_mood": round(avg_mood, 2),
            "top_themes": [t[0] for t in top_themes],
            "insights": insights,
            "ai_available": False
        })
    
    # Build AI prompt
    entries_summary = []
    for key in sorted(month_entries.keys())[-10:]:  # Last 10 entries of the month
        entry = month_entries[key]
        mood = entry.get("sentiment", {}).get("mood", "neutral")
        preview = entry.get("text", "")[:150]
        themes = entry.get("themes", [])
        day_name = datetime.strptime(key, "%Y-%m-%d").strftime("%A, %b %d")
        entries_summary.append(f"- {day_name} ({mood}): {preview}... [themes: {', '.join(themes) or 'general'}]")
    
    insights_text = "\n".join([f"- {i}" for i in insights]) if insights else "No strong patterns detected yet."
    
    system_prompt = """You are a thoughtful journaling companion providing a monthly reflection summary.

Create a warm, personalized summary that:
1. Acknowledges their journaling effort for this month
2. Identifies 2-3 specific patterns connecting activities, themes, and emotional states
   (e.g., "You mentioned feeling most energized when you wrote about outdoor activities.")
3. Highlights any notable moments or growth areas
4. Provides one personalized suggestion or encouragement based on what seems to resonate with them

Be specific and reference actual patterns from the data. Avoid generic advice.
Keep response under 200 words. Write warmly but concisely.
Format with short paragraphs for readability."""

    user_prompt = f"""Month: {month_name}

Stats:
- Total entries: {len(month_entries)}
- Mood trajectory: {mood_trajectory}
- Average mood score: {round(avg_mood, 2)} (-1 to 1 scale)
- Top themes: {', '.join([t[0] for t in top_themes]) if top_themes else 'varied'}

Sample entries:
{chr(10).join(entries_summary)}

Detected patterns:
{insights_text}

Best day: {best_day[0]} (mood: {best_day[1].get('sentiment', {}).get('mood', 'neutral')})
Most challenging day: {challenging_day[0]} (mood: {challenging_day[1].get('sentiment', {}).get('mood', 'neutral')})

Please provide a thoughtful monthly reflection."""

    try:
        summary = generate_text(system_prompt, user_prompt, max_tokens=300)
        return jsonify({
            "summary": summary,
            "month_name": month_name,
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "avg_mood": round(avg_mood, 2),
            "top_themes": [t[0] for t in top_themes],
            "insights": insights,
            "ai_available": True
        })
    except Exception as e:
        logger.error(f"Month summary AI error: {e}")
        return jsonify({
            "summary": f"In {month_name}, you wrote {len(month_entries)} entries with a {mood_trajectory} emotional trend.",
            "month_name": month_name,
            "entries_count": len(month_entries),
            "mood_trajectory": mood_trajectory,
            "avg_mood": round(avg_mood, 2),
            "top_themes": [t[0] for t in top_themes],
            "insights": insights,
            "ai_available": False,
            "error": str(e)
        })


# =============================================================================
# AI Feature Routes
# =============================================================================

@app.route("/api/rewrite", methods=["POST"])
@handle_errors
def rewrite():
    """AI-powered entry rewriting."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "No data provided"}), 400
    
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    if len(text) > MAX_ENTRY_LENGTH:
        return jsonify({"error": "Text too long"}), 400

    system_prompt = """You are a thoughtful writing assistant. Rewrite the user's journal entry 
to be clearer and more reflective. Guidelines:
- Keep the first-person voice
- Preserve the original meaning and emotions
- Maintain similar length
- Do not add new facts or change the narrative
- Output only the rewritten entry, nothing else."""

    try:
        result = generate_text(system_prompt, text, max_tokens=500)
        if result:
            return jsonify({"rewritten": result})
        return jsonify({"error": "AI not configured. Add GROQ_API_KEY to .env"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-from-nudges", methods=["POST"])
@handle_errors
def generate_from_nudges():
    """Generate a journal entry from quick nudges/notes."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "No data provided"}), 400
    
    nudges = body.get("nudges", [])
    date = body.get("date", "today")
    
    if not nudges or not isinstance(nudges, list):
        return jsonify({"error": "No nudges provided"}), 400
    
    if len(nudges) > 20:
        return jsonify({"error": "Too many nudges (max 20)"}), 400
    
    # Format nudges as bullet points
    nudges_text = "\n".join(f"- {n}" for n in nudges[:20])
    
    system_prompt = """You are a thoughtful journaling assistant. Transform the user's quick notes 
into a well-written, personal journal entry. Guidelines:

- Write in first person ("I")
- Create natural flowing prose, not bullet points
- Connect the moments into a cohesive narrative
- Add appropriate transitions between activities
- Include subtle emotional reflection where natural
- Keep it genuine and personal, not overly formal
- Length should be 2-4 paragraphs
- Do not invent facts not mentioned in the notes
- Output only the journal entry, nothing else."""

    user_prompt = f"Date: {date}\n\nMy notes for today:\n{nudges_text}\n\nWrite a journal entry from these moments:"

    try:
        result = generate_text(system_prompt, user_prompt, max_tokens=600)
        if result:
            return jsonify({"entry": result})
        return jsonify({"error": "AI not configured. Add GROQ_API_KEY to .env"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/suggest", methods=["POST"])
@handle_errors
def suggest():
    """Generate AI writing suggestions."""
    body = request.get_json()
    current_text = body.get("text", "").strip() if body else ""
    
    data = load_data()
    
    # Get recent entries for context
    recent = []
    for key in sorted(data["entries"].keys(), reverse=True)[:3]:
        preview = data["entries"][key].get("text", "")[:100]
        mood = data["entries"][key].get("sentiment", {}).get("mood", "neutral")
        if preview:
            recent.append(f"- {key} ({mood}): {preview}")
    
    context = "\n".join(recent) if recent else "No previous entries."
    
    system_prompt = """You are a supportive journaling assistant. Generate exactly 3 personalized 
writing suggestions as JSON. Based on the draft and recent entries, provide:

1. A continuation suggestion (help expand the current thought)
2. A reflection prompt (help think deeper about feelings)
3. A gratitude reframe (find something positive)

Consider the user's recent mood patterns and be appropriately supportive.
Keep each suggestion under 40 words. Be warm but not cheesy.

Output ONLY valid JSON in this exact format:
{"suggestions": [{"type": "continue", "text": "..."}, {"type": "reflect", "text": "..."}, {"type": "gratitude", "text": "..."}]}"""

    user_prompt = f"Current draft:\n{current_text or '(empty - just started)'}\n\nRecent entries:\n{context}"

    try:
        result = generate_text(system_prompt, user_prompt, max_tokens=300)
        if not result:
            return jsonify({"error": "AI not configured. Add GROQ_API_KEY to .env"}), 500
        
        # Parse JSON from response
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            return jsonify(suggestions)
        return jsonify({"error": "Failed to parse suggestions"}), 500
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid AI response format"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/summarize", methods=["POST"])
@handle_errors
def summarize():
    """Generate AI summary of an entry."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "No data provided"}), 400
    
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Get sentiment for context
    sentiment = analyze_sentiment(text)
    mood_context = f"The entry has a {sentiment['mood']} tone."

    system_prompt = f"""Summarize this journal entry in 1-2 sentences.
{mood_context}
Capture the main emotion and key event. Be concise, warm, and empathetic.
Output only the summary, nothing else."""

    try:
        result = generate_text(system_prompt, text, max_tokens=100)
        if result:
            return jsonify({
                "summary": result,
                "sentiment": sentiment
            })
        return jsonify({"error": "AI not configured. Add GROQ_API_KEY to .env"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Data Management Routes
# =============================================================================

@app.route("/api/export", methods=["GET"])
@handle_errors
def export_data():
    """Export all journal data."""
    data = load_data()
    data["exported_at"] = datetime.now().isoformat()
    data["version"] = "1.0"
    return jsonify(data)


@app.route("/api/import", methods=["POST"])
@handle_errors
def import_data():
    """Import journal data from backup."""
    body = request.get_json()
    
    if not body or not isinstance(body, dict):
        return jsonify({"error": "Invalid data format"}), 400
    
    if "entries" not in body:
        return jsonify({"error": "Missing 'entries' field"}), 400
    
    # Validate entries
    if not isinstance(body["entries"], dict):
        return jsonify({"error": "Invalid entries format"}), 400
    
    # Add import metadata
    body["metadata"] = body.get("metadata", {})
    body["metadata"]["imported_at"] = datetime.now().isoformat()
    
    if save_data(body):
        return jsonify({
            "imported": True,
            "entries_count": len(body["entries"])
        })
    return jsonify({"error": "Failed to save imported data"}), 500


@app.route("/api/clear", methods=["DELETE"])
@handle_errors
def clear_data():
    """Clear all journal data."""
    if save_data({"entries": {}, "metadata": {"cleared_at": datetime.now().isoformat()}}):
        return jsonify({"cleared": True})
    return jsonify({"error": "Failed to clear data"}), 500


# =============================================================================
# Privacy Info Route
# =============================================================================

@app.route("/api/privacy", methods=["GET"])
def privacy_info():
    """Return privacy information."""
    return jsonify({
        "data_location": "local",
        "cloud_sync": False,
        "encryption": "optional",
        "data_sharing": "none",
        "message": "Your journal is private. All data stays on your device. No cloud uploads, no tracking, no ads."
    })


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting Reflect AI server...")
    logger.info("Privacy-first design: All data stays local")
    app.run(debug=True, port=5000)
