from flask import Flask, request, jsonify, render_template, redirect, make_response
import sqlite3, json, os

app = Flask(__name__)
ADMIN_PASSWORD = "die"
CLIENT_TOKEN   = "SutCrvUnygZcmNznqreDrRzSfF3Basmk"

DB = "data.db"

# ─── База данных ─────────────────────────────────────────────────────────────

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        buttons TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        button_clicked TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    c.commit(); c.close()

init_db()

# ─── API для клиентской программы ────────────────────────────────────────────

@app.route('/api/check')
def api_check():
    if request.headers.get('X-Token') != CLIENT_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    c = db()
    msg = c.execute(
        "SELECT * FROM messages WHERE status='pending' ORDER BY id LIMIT 1"
    ).fetchone()
    if msg:
        c.execute("UPDATE messages SET status='sent' WHERE id=?", (msg['id'],))
        c.commit(); c.close()
        return jsonify({
            'message_id': msg['id'],
            'text': msg['text'],
            'buttons': json.loads(msg['buttons'])
        })
    c.close()
    return jsonify({'message_id': None})

@app.route('/api/response', methods=['POST'])
def api_response():
    if request.headers.get('X-Token') != CLIENT_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    c = db()
    c.execute("INSERT INTO responses (message_id, button_clicked) VALUES (?,?)",
              (data['message_id'], data['button_clicked']))
    c.execute("UPDATE messages SET status='answered' WHERE id=?", (data['message_id'],))
    c.commit(); c.close()
    return jsonify({'ok': True})

# ─── Админ панель ─────────────────────────────────────────────────────────────

def logged_in():
    return request.cookies.get('auth') == ADMIN_PASSWORD

@app.route('/')
def index():
    return redirect('/admin')

@app.route('/admin', methods=['GET','POST'])
def admin():
    error = None
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            if request.form.get('password') == ADMIN_PASSWORD:
                r = make_response(redirect('/admin'))
                r.set_cookie('auth', ADMIN_PASSWORD, max_age=86400*30)
                return r
            error = 'Неверный пароль'

        elif action == 'logout':
            r = make_response(redirect('/admin'))
            r.delete_cookie('auth')
            return r

        elif action == 'send' and logged_in():
            text = request.form.get('text','').strip()
            buttons = [b.strip() for b in request.form.getlist('btn[]') if b.strip()]
            if text:
                if not buttons: buttons = ['ОК']
                c = db()
                c.execute("INSERT INTO messages (text,buttons) VALUES (?,?)",
                          (text, json.dumps(buttons, ensure_ascii=False)))
                c.commit(); c.close()
            return redirect('/admin')

        elif action == 'delete' and logged_in():
            mid = request.form.get('msg_id')
            c = db()
            c.execute("DELETE FROM responses WHERE message_id=?", (mid,))
            c.execute("DELETE FROM messages WHERE id=?", (mid,))
            c.commit(); c.close()
            return redirect('/admin')

    if not logged_in():
        return render_template('admin.html', logged_in=False, error=error)

    c = db()
    rows = c.execute("""
        SELECT m.id, m.text, m.buttons, m.status, m.created_at,
               r.button_clicked, r.created_at as resp_time
        FROM messages m
        LEFT JOIN responses r ON m.id = r.message_id
        ORDER BY m.id DESC LIMIT 100
    """).fetchall()
    c.close()

    messages = []
    for row in rows:
        msg = dict(row)
        msg['buttons_list'] = json.loads(msg['buttons'])
        messages.append(msg)

    return render_template('admin.html', logged_in=True, messages=messages, error=None)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)