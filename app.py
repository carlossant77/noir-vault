from flask import Flask, request, redirect, session, render_template
import sqlite3
import hashlib
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'chave_secreta'

conn = sqlite3.connect('noir.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT UNIQUE,
        senha TEXT
    )
''')
conn.commit()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

@app.route('/')
def home():
    if 'usuario_id' in session:
        return render_template('index.html', logado=True, usuario=session['usuario'])
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['password']
        
        cursor.execute(
            "SELECT id, nome FROM usuarios WHERE email = ? AND senha = ?",
            (email, hash_senha(senha))
        )
        usuario = cursor.fetchone()
        
        if usuario:
            session['usuario_id'] = usuario[0]
            session['usuario'] = usuario[1]
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
        
        try:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)",
                (nome, email, hash_senha(senha))
            )
            conn.commit()
            return redirect('/login')
        except:
            return render_template('cadastro.html', erro="Email já existe!")
    
    return render_template('cadastro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)