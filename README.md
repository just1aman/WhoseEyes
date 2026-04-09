# Whose Eyes?

A multiplayer party game where players upload close-up photos of their eyes and everyone tries to guess whose eyes belong to whom. Faster correct guesses earn more points.

**Live at:** https://whoseeyes-just1aman.pythonanywhere.com/

## How It Works

1. **Host** creates a room and gets a 6-letter code
2. **Players** join using the code
3. Everyone **uploads** a cropped photo of just their eyes
4. Host **starts** the round — each player sees shuffled eye photos and matches them to names
5. **Scoring:** 100 base points per correct guess + up to 50 speed bonus (decays over 60 seconds)
6. **Results** show the leaderboard, your guess breakdown, and the big reveal

## Tech Stack

- **Backend:** Python, Flask, SQLAlchemy, SQLite
- **Frontend:** HTML, CSS, vanilla JavaScript (no frameworks)
- **Image processing:** Pillow (auto-crops to 2:1 aspect ratio, resizes to 400x200)
- **Async polling:** pages auto-refresh (no WebSockets)

## Run Locally

```bash
git clone https://github.com/just1aman/WhoseEyes.git
cd WhoseEyes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Project Structure

```
WhoseEyes/
  app.py              # Flask app — models, routes, image processing
  requirements.txt    # Python dependencies
  templates/
    base.html         # Shared layout with header
    index.html        # Home — create or join a room
    room.html         # Lobby — player list, upload status, start button
    upload.html       # Eye photo upload with drag-and-drop
    game.html         # Guessing screen with timer
    results.html      # Leaderboard + guess breakdown + reveal
  static/
    css/style.css     # Dark-themed UI
    js/main.js        # Shared utilities
  uploads/            # Player eye photos (git-ignored)
```

## PythonAnywhere Deployment

1. Clone repo in a PythonAnywhere Bash console
2. Create venv and install dependencies
3. Create a **Manual configuration** web app matching your Python version
4. Set WSGI file to:
   ```python
   import sys
   path = '/home/YOUR_USERNAME/WhoseEyes'
   if path not in sys.path:
       sys.path.insert(0, path)
   from app import app as application
   ```
5. Set virtualenv path to `/home/YOUR_USERNAME/WhoseEyes/.venv`
6. Add static file mapping: `/static/` -> `/home/YOUR_USERNAME/WhoseEyes/static`
7. If you get a "no such table" error, run:
   ```bash
   cd ~/WhoseEyes && source .venv/bin/activate
   python -c "from app import db, app; app.app_context().push(); db.create_all()"
   ```
8. Reload the web app
