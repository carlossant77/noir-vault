from flask import Flask, request, redirect, session, render_template
import sqlite3
import hashlib
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'chave_secreta'


def get_db():
    conn = sqlite3.connect('noir.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT UNIQUE,
            senha TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


@app.route('/')
def home():
    return render_template(
        'index.html',
        logado=('usuario' in session),
        usuario=session.get('usuario'),
        is_admin=session.get('is_admin', False)
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nome, is_admin FROM usuarios WHERE email = ? AND senha = ?",
            (email, hash_senha(senha))
        )
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario['id']
            session['usuario'] = usuario['nome']
            session['is_admin'] = bool(usuario['is_admin'])
            return redirect('/')
        else:
            return render_template('login.html', erro="Email ou senha incorretos!")

    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['username']
        email = request.form['email']
        senha = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)",
                (nome, email, hash_senha(senha))
            )
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('cadastro.html', erro="Email já existe!")

    return render_template('cadastro.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)