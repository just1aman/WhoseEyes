import os
import random
import string
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from PIL import Image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "whose_eyes.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

db = SQLAlchemy(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

with app.app_context():
    db.create_all()


# ─── Models ───────────────────────────────────────────────────────────────────


class Room(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    code       = db.Column(db.String(6), unique=True, nullable=False)
    status     = db.Column(db.String(20), default="lobby")  # lobby | playing | finished
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    players    = db.relationship("Player", backref="room", lazy=True,
                                 foreign_keys="Player.room_id")


class Player(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(50), nullable=False)
    room_id      = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    session_id   = db.Column(db.String(64), nullable=False)
    score        = db.Column(db.Integer, default=0)
    has_uploaded = db.Column(db.Boolean, default=False)
    has_guessed  = db.Column(db.Boolean, default=False)
    is_host      = db.Column(db.Boolean, default=False)
    image_path   = db.Column(db.String(300), nullable=True)


class Guess(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    guesser_id        = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    photo_player_id   = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    guessed_player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    correct           = db.Column(db.Boolean, nullable=False)
    time_taken        = db.Column(db.Float, nullable=False)
    points            = db.Column(db.Integer, default=0)
    guesser           = db.relationship("Player", foreign_keys=[guesser_id])
    photo_player      = db.relationship("Player", foreign_keys=[photo_player_id])
    guessed_player    = db.relationship("Player", foreign_keys=[guessed_player_id])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def make_room_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=6))
        if not Room.query.filter_by(code=code).first():
            return code


def get_current_player(room):
    sid = session.get("session_id")
    if not sid:
        return None
    return Player.query.filter_by(room_id=room.id, session_id=sid).first()


@app.context_processor
def inject_current_user_name():
    sid = session.get("session_id")
    if sid:
        player = Player.query.filter_by(session_id=sid).order_by(Player.id.desc()).first()
        if player:
            return {"current_user_name": player.name}
    return {"current_user_name": None}


def calc_points(time_taken):
    """100 base + up to 50 speed bonus (decays to 0 at 60 s)."""
    speed_bonus = max(0, int(50 * (1 - min(time_taken, 60) / 60)))
    return 100 + speed_bonus


def process_eye_image(stream):
    """Open, centre-crop to 2:1 aspect ratio, resize to 400×200."""
    img = Image.open(stream).convert("RGB")
    w, h = img.size
    target_ratio = 2.0
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img.resize((400, 200), Image.LANCZOS)


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create_room():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Please enter your name.")
        return redirect(url_for("index"))

    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()

    room = Room(code=make_room_code())
    db.session.add(room)
    db.session.flush()

    player = Player(name=name, room_id=room.id,
                    session_id=session["session_id"], is_host=True)
    db.session.add(player)
    db.session.commit()
    return redirect(url_for("room_lobby", code=room.code))


@app.route("/join", methods=["POST"])
def join_room():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()

    if not name or not code:
        flash("Name and room code are required.")
        return redirect(url_for("index"))

    room = Room.query.filter_by(code=code).first()
    if not room:
        flash("Room not found. Check the code and try again.")
        return redirect(url_for("index"))
    if room.status != "lobby":
        flash("That game has already started.")
        return redirect(url_for("index"))

    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()

    existing = Player.query.filter_by(room_id=room.id,
                                      session_id=session["session_id"]).first()
    if not existing:
        player = Player(name=name, room_id=room.id,
                        session_id=session["session_id"])
        db.session.add(player)
        db.session.commit()

    return redirect(url_for("room_lobby", code=code))


@app.route("/room/<code>")
def room_lobby(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)
    if not player:
        flash("You are not in this room.")
        return redirect(url_for("index"))
    if room.status == "playing":
        return redirect(url_for("game", code=code))
    if room.status == "finished":
        return redirect(url_for("results", code=code))
    return render_template("room.html", room=room, player=player,
                           players=room.players)


@app.route("/upload/<code>", methods=["GET", "POST"])
def upload(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)
    if not player:
        return redirect(url_for("index"))
    if room.status != "lobby":
        return redirect(url_for("room_lobby", code=code))

    if request.method == "POST":
        f = request.files.get("photo")
        if not f or f.filename == "":
            flash("Please select an image file.")
            return redirect(url_for("upload", code=code))

        try:
            img = process_eye_image(f.stream)
        except Exception:
            flash("Could not read image. Please try a JPG or PNG file.")
            return redirect(url_for("upload", code=code))

        filename = f"player_{player.id}.jpg"
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        img.save(path, "JPEG", quality=85)

        player.image_path = path
        player.has_uploaded = True
        db.session.commit()
        return redirect(url_for("room_lobby", code=code))

    return render_template("upload.html", room=room, player=player)


@app.route("/start/<code>", methods=["POST"])
def start_game(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)
    if not player or not player.is_host:
        abort(403)

    uploaded = [p for p in room.players if p.has_uploaded]
    if len(uploaded) < 2:
        flash("Need at least 2 players with uploaded photos to start.")
        return redirect(url_for("room_lobby", code=code))

    room.status = "playing"
    room.started_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("game", code=code))


@app.route("/game/<code>")
def game(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)
    if not player:
        return redirect(url_for("index"))
    if room.status == "lobby":
        return redirect(url_for("room_lobby", code=code))
    if room.status == "finished":
        return redirect(url_for("results", code=code))

    # Photos to guess: all uploaded players except self
    photo_players = [p for p in room.players if p.has_uploaded]
    others = [p for p in photo_players if p.id != player.id]

    # Shuffle deterministically per player so everyone sees different order
    rng = random.Random(room.id * 10000 + player.id)
    rng.shuffle(others)

    # Name options = same set (you can't be the answer to your own missing photo)
    name_options = sorted(others, key=lambda p: p.name)

    started_ts = room.started_at.timestamp() if room.started_at else 0

    return render_template("game.html", room=room, player=player,
                           photo_players=others,
                           name_options=name_options,
                           already_guessed=player.has_guessed,
                           started_ts=started_ts)


@app.route("/guess/<code>", methods=["POST"])
def submit_guess(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)
    if not player or room.status != "playing" or player.has_guessed:
        return redirect(url_for("game", code=code))

    time_taken = (datetime.utcnow() - room.started_at).total_seconds()
    photo_players = [p for p in room.players if p.has_uploaded and p.id != player.id]
    total_points = 0

    for pp in photo_players:
        raw = request.form.get(f"guess_{pp.id}", "").strip()
        if not raw:
            continue
        try:
            guessed_id = int(raw)
        except ValueError:
            continue

        correct = guessed_id == pp.id
        pts = calc_points(time_taken) if correct else 0
        total_points += pts

        db.session.add(Guess(
            guesser_id=player.id,
            photo_player_id=pp.id,
            guessed_player_id=guessed_id,
            correct=correct,
            time_taken=time_taken,
            points=pts,
        ))

    player.score += total_points
    player.has_guessed = True
    db.session.commit()

    # End the round once every uploaded player has guessed
    uploaded = Player.query.filter_by(room_id=room.id, has_uploaded=True).all()
    if all(p.has_guessed for p in uploaded):
        room.status = "finished"
        db.session.commit()

    return redirect(url_for("results", code=code))


@app.route("/results/<code>")
def results(code):
    room = Room.query.filter_by(code=code).first_or_404()
    player = get_current_player(room)

    leaderboard = sorted(room.players, key=lambda p: p.score, reverse=True)

    my_guesses = []
    if player:
        my_guesses = Guess.query.filter_by(guesser_id=player.id).all()

    return render_template("results.html", room=room, player=player,
                           leaderboard=leaderboard, my_guesses=my_guesses)


@app.route("/image/<int:player_id>")
def player_image(player_id):
    p = Player.query.get_or_404(player_id)
    if not p.image_path or not os.path.exists(p.image_path):
        abort(404)
    return send_file(p.image_path, mimetype="image/jpeg")


@app.route("/api/room/<code>/status")
def room_status(code):
    room = Room.query.filter_by(code=code).first_or_404()
    return jsonify({
        "status": room.status,
        "players": [
            {"name": p.name, "has_uploaded": p.has_uploaded,
             "has_guessed": p.has_guessed, "score": p.score}
            for p in room.players
        ],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
