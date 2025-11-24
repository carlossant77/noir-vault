from flask import Flask, request, redirect, session, render_template
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os

 
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'chave_secreta'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
 
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@socketio.on('login_check')
def login_check():
    if session.get('usuario'):
        emit('change_page', { 'url': '/perfil' } ) 
    else:
        emit('open_modal')
        
@socketio.on('salvarFoto')
def salvar_foto(data):
    
    url = data.get('url')
    email = session.get('email')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
                    UPDATE usuarios 
                    SET foto = ? 
                    WHERE email = ?
                ''', (url, email))
    
    conn.commit()
    conn.close()
    
    session['foto'] = url
    
 
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
            foto TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')
 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            produto_id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            tamanho TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco INTEGER NOT NULL,
            foto TEXT
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
            logado=True,
            usuario=session['usuario'] if 'usuario' in session else None,
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
            "SELECT id, nome, email, is_admin FROM usuarios WHERE email = ? AND senha = ?",
            (email, hash_senha(senha))
        )
        usuario = cursor.fetchone()
        conn.close()
 
        if usuario:
            session['usuario_id'] = usuario['id']
            session['usuario'] = usuario['nome']
            session['email'] = email
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
 
 
@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session:
        return redirect('/login')
 
    if not session.get('is_admin', False):
        return "Acesso negado! Você precisa ser administrador.", 403
 
    if request.method == 'POST':
        nome = request.form['nome']
        tipo = request.form['tipo']
        tamanho = request.form.get('tamanho', '')
        quantidade = int(request.form['quantidade'])
        preco = int(float(request.form['preco'].replace(',', '.')) * 100)
 
        foto = request.files.get('foto')
        foto_filename = None
        if foto and foto.filename != '':
            foto_filename = secure_filename(foto.filename)
            foto.save(os.path.join(UPLOAD_FOLDER, foto_filename))
 
        with sqlite3.connect('noir.db', timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO produtos (nome, tipo, tamanho, quantidade, preco, foto) VALUES (?, ?, ?, ?, ?, ?)",
                (nome, tipo, tamanho, quantidade, preco, foto_filename)
            )
            conn.commit()
 
    with sqlite3.connect('noir.db', timeout=10, check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM produtos ORDER BY produto_id DESC")
        produtos_lista = cursor.fetchall()
 
    return render_template('produto.html', produtos=produtos_lista)

@app.route('/perfil')
def perfil():
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT foto FROM usuarios WHERE email = ?', (session.get('email'),))
    url = cursor.fetchone()
    
    return render_template('perfil.html', 
                           usuario=session.get('usuario'), 
                           email=session.get('email'),
                           foto=url if url != '' or None else None)
        

@app.route('/wishlist')
def wishlist():
    return render_template('wishlist.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
 
 
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
    socketio.run(app, debug=True)