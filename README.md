# Reflect AI - Your Private AI-Powered Journal

> 🎬 **[Watch the Demo Video](https://youtu.be/RrkTxPldSfU)** — See Reflect AI in action!

A modern, privacy-first journaling companion that helps you maintain a consistent reflection habit through personalized insights, beautiful visualizations, and AI-powered features. All your data stays local and private.

## 🌟 Features

### Core Journaling
- **Calendar-Based Entry Management**: Browse entries by month or year with beautiful calendar view
- **Streak Tracking**: Maintain motivation with visual streak counters and weekly completion chain
- **Achievement Badges**: Unlock badges as you hit reflection milestones (100 entries, 7-day streak, etc.)
- **Auto-Mood Detection**: Real-time sentiment analysis using VADER NLP
- **Smart Prompts**: Jump-start writing with pre-built prompts (Gratitude, Reflection, Goals, Emotions)

### Advanced Analytics
- **Interactive Dashboards**: Beautiful Chart.js visualizations of your journaling patterns
- **Mood Trends**: Line charts showing emotional journey throughout the month
- **Mood Distribution**: Pie charts of your emotional balance
- **Activity Analysis**: See which days of the week you journal most
- **Theme Extraction**: Automatic identification of recurring topics in your entries
- **AI-Generated Insights**: Smart patterns detection using Groq AI (mood trajectory, best days, top themes)
- **Weekly & Monthly Summaries**: AI-powered reflection on your entries using Groq

### User Experience
- **Dark/Light Theme Toggle**: Switch between themes with persistent preference storage
- **Real-time Last Saved Status**: Know exactly when your entry was saved
- **Responsive Design**: Works beautifully on desktop, tablet, and mobile
- **Weather Integration**: See the weather from when you wrote each entry
- **Import/Export**: Backup and restore your journal data as JSON
- **Word Count Tracking**: Monitor how much you're writing

## 🔒 Privacy & Security

- ✅ **100% Local Storage**: All data stored in `journal_data.json` on your device
- ✅ **No Cloud Sync**: Complete control over your personal reflections
- ✅ **No External Analytics**: No tracking, no telemetry
- ✅ **Groq API Required**: Uses Groq for AI features (free tier available at console.groq.com)
- ✅ **Data Ownership**: You can export your data anytime

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask (Python REST API)
- **Sentiment Analysis**: NLTK VADER sentiment scorer
- **NLP**: NLTK for text processing and analysis
- **AI**: Groq API for intelligent insights and greetings
- **Language**: Python 3.9+

### Frontend
- **UI Framework**: JavaScript (plain, no framework dependencies)
- **Styling**: Custom CSS with CSS Variables for theming
- **Charts**: Chart.js for beautiful visualizations
- **Icons**: Emoji + SVG icons

### Data Storage
- **Format**: JSON (human-readable, portable)
- **Location**: `journal_data.json` (local filesystem)

## 📦 Installation

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- ~500MB disk space for optional AI models

### Step 1: Clone/Download Project

```bash
cd "PANW Hackathon Code"
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `flask` - Web framework
- `flask-cors` - Cross-origin requests
- `python-dotenv` - Environment variable management
- `groq` - Groq API client for AI features
- `nltk` - Natural Language Toolkit for sentiment analysis

### Step 3: Download NLTK Data (First Run Only)

```bash
python3 -c "import nltk; nltk.download('vader_lexicon')"
```

### Step 4: Set up Groq API Key

Get a free API key from [console.groq.com](https://console.groq.com), then create a `.env` file:

```bash
echo 'GROQ_API_KEY="your_api_key_here"' > .env
```

## 🚀 Running the App

### Start the Server

```bash
python3 app.py
```

You'll see output like:
```
2026-01-31 21:41:42,357 - INFO - Starting Reflect AI server...
2026-01-31 21:41:42,357 - INFO - Privacy-first design: All data stays local
* Running on http://127.0.0.1:5000
```

### Access the App

Open your browser and go to:
```
http://127.0.0.1:5000
```

The app will load with a personalized greeting and your journal ready to use.

## 📁 Project Structure

```
PANW Hackathon Code/
├── app.py                    # Flask backend (1947 lines)
├── index.html               # Main HTML shell
├── static/
│   ├── app.js              # Frontend logic (1424 lines)
│   ├── styles.css          # Styling with theme support (1098 lines)
│   └── [assets]
├── journal_data.json        # Your entries (auto-created)
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🎯 How to Use

### Writing Your First Entry

1. Click **"Write Today"** or click any date on the calendar
2. Choose a prompt type or write freely
3. Write your reflection
4. Click **Save** - mood is automatically detected
5. See your entry appear on the calendar with a mood emoji

### Exploring Your Journal

**Month View (Default)**
- Calendar shows all entries for the current month
- Color-coded by mood
- Click any date to view/edit that day's entry
- Navigation arrows to browse previous/future months

**Year View**
- See all months in a compact grid
- Shows entry count per month
- Click any month to switch to month view

**Insights View**
- Beautiful dashboard with 6 interactive charts:
  - Mood Trend Line Chart
  - Emotional Balance Pie Chart
  - Writing Patterns by Day
  - Topics You've Explored
  - Weekly Writing Consistency
  - Your Reflection Depth (Word Count)
- AI-Generated insights about your patterns

### Tracking Progress

**Streak Tracker**
- Visual progress ring showing current day streak
- Weekly completion chain (M-S)
- Streak alert warns when at risk

**Achievement Badges**
- Unlocked as you hit milestones:
  - First Entry
  - 7-Day Streak
  - 30 Entries
  - 100 Entries
  - etc.

### Advanced Features

**AI-Powered Insights**
- Groq API generates smart insights about your mood patterns
- AI summaries of your weekly and monthly entries
- Personalized greetings based on your journaling history

**Export Your Data**
- Click **Export** to download `journal_backup.json`
- Your complete journal in portable format

**Import Data**
- Click **Import** to restore from a backup
- Merges with existing entries safely

**Dark Mode**
- Click the 🌙 button in the header
- Theme preference saved automatically

## 🔧 Configuration

### Required: Groq API Key

The app requires a Groq API key for AI features:

1. Get a free API key from [console.groq.com](https://console.groq.com)
2. Create a `.env` file in the project directory:
   ```bash
   GROQ_API_KEY="your_key_here"
   ```
3. Restart the app - AI features will be active

The free tier of Groq is sufficient for personal journaling use.

## 📊 API Endpoints

The Flask backend provides these REST endpoints:

```
GET  /api/entries              # Get all entries
POST /api/entries              # Create new entry
PUT  /api/entries/<id>         # Update entry
DEL  /api/entries/<id>         # Delete entry

GET  /api/stats                # Get statistics
GET  /api/insights/charts      # Get chart data
GET  /api/insights/summary     # Get AI summary
GET  /api/greeting             # Get personalized greeting

POST /api/rewrite              # Rewrite text with AI
GET  /api/suggest              # Get AI suggestions
GET  /api/weekly               # Weekly insights
GET  /api/monthly              # Monthly summary
GET  /api/export               # Export data
POST /api/import               # Import data
```

## 🎨 Customization

### Change Colors/Theme

Edit `static/styles.css`:
```css
:root {
  --accent: #2563eb;           /* Primary blue */
  --success: #16a34a;          /* Success green */
  --danger: #dc2626;           /* Danger red */
  /* ... more colors */
}
```

Dark theme overrides are in the `body.dark-theme` section.

### Adjust Chart Heights

In `static/styles.css`:
```css
.chart-container {
  height: 200px;  /* Adjust this */
}
```

### Customize Prompts

Edit `static/app.js`, search for `PROMPTS` object to add your own writing prompts.

## 🐛 Troubleshooting

### Port Already in Use

If you see "Address already in use", kill the process:
```bash
# On macOS/Linux
lsof -ti:5000 | xargs kill -9

# Or use a different port
python3 app.py --port 5001
```

### Missing NLTK Data

If you get VADER errors:
```bash
python3 -c "import nltk; nltk.download('vader_lexicon')"
```

### Data Not Saving

Check that `journal_data.json` is writable:
```bash
chmod 644 journal_data.json
```

### Dark Theme Not Persisting

Clear browser localStorage and try again:
- Dev Tools → Application → Local Storage → Clear

## 📈 Performance Tips

- **Faster Charts**: App caches chart data - refresh page if data seems stale
- **Bulk Import**: Large imports work fine (tested with 1000+ entries)
- **Mobile**: Use landscape mode for better chart visibility
- **Search**: Use browser Find (Ctrl+F) to search calendar

## 📝 Data Format

Your entries are stored in JSON:

```json
{
  "2026-01-31": {
    "id": "uuid",
    "text": "Today was a good day...",
    "mood": "positive",
    "mood_score": 0.65,
    "timestamp": "2026-01-31T15:30:00",
    "tags": [],
    "word_count": 145
  }
}
```

## 🔐 Security Notes

- **File Permissions**: `journal_data.json` is local only
- **No Authentication**: Single-user, local device
- **Data Backups**: Use Export feature regularly
- **Browser Storage**: Theme preference stored in localStorage (non-sensitive)

##  License

This project was created for the PANW Hackathon Challenge 2026.

## 🙏 Acknowledgments

- NLTK for sentiment analysis
- Groq for AI-powered insights
- Chart.js for beautiful visualizations
- The journaling community for inspiration

---

**Happy Reflecting! 🌟**

All your thoughts, your space, your growth.
