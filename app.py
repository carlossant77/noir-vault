from flask import Flask, request, redirect, session, render_template, g, jsonify
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
import requests # Importação necessária para a API ViaCEP
import re # Para validar a avaliação

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'chave_secreta'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- BANCO DE DADOS ----------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('noir.db', timeout=30, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
        g.db.execute("PRAGMA busy_timeout = 30000;")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect('noir.db')
    cursor = conn.cursor()

    # Tabela usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT UNIQUE,
            senha TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    # Tabela produtos (Adicionado descricao e tamanho_disponivel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            produto_id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            tamanho TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco INTEGER NOT NULL,
            foto TEXT,
            descricao TEXT, 
            tamanhos_disponiveis TEXT DEFAULT 'PP,P,M,G,GG'
        )
    ''')
    
    # Tabela avaliações (Nova tabela)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            nota REAL NOT NULL, -- Nota de 0 a 5
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(produto_id),
            UNIQUE(usuario_id, produto_id) -- Garante apenas 1 avaliação por usuário/produto
        )
    ''')

    # Tabela carrinho (CORREÇÃO: Adicionada a coluna tamanho_selecionado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carrinho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco REAL NOT NULL,
            cupom TEXT,
            tamanho_selecionado TEXT, -- NOVO CAMPO PARA O TAMANHO SELECIONADO
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(produto_id)
        )
    ''')

    # Tabela cupom
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cupom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cupom TEXT UNIQUE,
            desconto REAL NOT NULL
        )
    ''')
    
    # Adiciona a coluna 'descricao' se não existir
    try:
        cursor.execute("SELECT descricao FROM produtos LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE produtos ADD COLUMN descricao TEXT")
    
    # Adiciona a coluna 'tamanhos_disponiveis' se não existir
    try:
        cursor.execute("SELECT tamanhos_disponiveis FROM produtos LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE produtos ADD COLUMN tamanhos_disponiveis TEXT DEFAULT 'PP,P,M,G,GG'")
        
    # Adiciona a coluna 'tamanho_selecionado' na tabela carrinho se não existir (CORREÇÃO)
    try:
        cursor.execute("SELECT tamanho_selecionado FROM carrinho LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE carrinho ADD COLUMN tamanho_selecionado TEXT")
        
    conn.commit()
    conn.close()


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


# Função auxiliar para obter a avaliação média
def get_media_avaliacao(produto_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT AVG(nota) as media, COUNT(nota) as total FROM avaliacoes WHERE produto_id = ?", (produto_id,))
    resultado = cursor.fetchone()
    if resultado and resultado['total'] > 0:
        return round(resultado['media'], 1), resultado['total']
    return 0.0, 0


# ---------- ROTAS DE PRODUTO INDIVIDUAL E AVALIAÇÃO ----------

@app.route('/produto/<int:produto_id>')
def detalhe_produto(produto_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Busca o produto
    cursor.execute("SELECT * FROM produtos WHERE produto_id = ?", (produto_id,))
    produto = cursor.fetchone()

    if not produto:
        return "Produto não encontrado", 404

    # Calcula a média de avaliações
    media, total_avaliacoes = get_media_avaliacao(produto_id)
    
    # Prepara os dados para o template
    produto_dict = dict(produto)
    produto_dict['preco_display'] = "{:.2f}".format(produto_dict['preco'] / 100.0)
    produto_dict['media_avaliacao'] = media
    produto_dict['total_avaliacoes'] = total_avaliacoes
    produto_dict['tamanhos'] = produto_dict['tamanhos_disponiveis'].split(',')

    # Verifica a avaliação do usuário logado, se houver
    avaliacao_usuario = None
    if 'usuario_id' in session:
        usuario_id = session['usuario_id']
        cursor.execute(
            "SELECT nota FROM avaliacoes WHERE usuario_id = ? AND produto_id = ?",
            (usuario_id, produto_id)
        )
        user_rating = cursor.fetchone()
        if user_rating:
            avaliacao_usuario = user_rating['nota']

    return render_template(
        'produto.html',
        produto=produto_dict,
        logado='usuario_id' in session,
        usuario=session.get('usuario'),
        is_admin=session.get('is_admin', False),
        avaliacao_usuario=avaliacao_usuario # Avaliação anterior do usuário
    )


@app.route('/avaliar_produto/<int:produto_id>', methods=['POST'])
def avaliar_produto(produto_id):
    if 'usuario_id' not in session:
        return jsonify({"erro": "Você precisa estar logado para avaliar."}), 401

    try:
        # A nota vem como string do JS, ex: "3.5"
        nota_str = request.form.get('nota')
        
        # 1. Validação do formato: 0 a 5, apenas .5 de casa decimal (ex: 1, 1.5, 2, 2.5, ..., 5)
        # O regex verifica se a string é:
        # - Um dígito de 0 a 4, opcionalmente seguido por .5 (ex: "3.5", "4")
        # - Ou exatamente 5 (ex: "5")
        if not re.fullmatch(r"([0-4](\.5)?)|\s*5\s*", nota_str.strip()):
            return jsonify({"erro": "Nota inválida. Use valores de 0 a 5, com incrementos de 0.5 (ex: 1, 1.5, 3.5)."}), 400
            
        nota = float(nota_str)
        
        # 2. Validação do valor (redundante, mas seguro)
        if not (0.0 <= nota <= 5.0):
            return jsonify({"erro": "Nota deve estar entre 0 e 5."}), 400

    except ValueError:
        return jsonify({"erro": "Formato de nota inválido."}), 400

    usuario_id = session['usuario_id']
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Tenta inserir (se o usuário ainda não avaliou) ou atualizar (se já avaliou)
        # Usamos INSERT OR REPLACE para garantir que cada usuário só tenha uma avaliação por produto
        cursor.execute(
            "INSERT OR REPLACE INTO avaliacoes (usuario_id, produto_id, nota) VALUES (?, ?, ?)",
            (usuario_id, produto_id, nota)
        )
        conn.commit()

        # Recalcula a média após a inserção/atualização
        media_nova, total_avaliacoes_novo = get_media_avaliacao(produto_id)

        return jsonify({
            "sucesso": True,
            "mensagem": "Avaliação salva com sucesso!",
            "media_avaliacao": media_nova,
            "total_avaliacoes": total_avaliacoes_novo
        })

    except Exception as e:
        print(f"Erro ao salvar avaliação: {e}")
        return jsonify({"erro": "Erro interno ao salvar a avaliação."}), 500


# ---------- ROTAS EXISTENTES (Ajustadas para a nova estrutura de produtos e carrinho) ----------

@app.route('/')
def home():
    # CORREÇÃO: A rota home estava assumindo que o usuário estava sempre logado (logado=True),
    # mas o template deve verificar a sessão.
    return render_template(
        'index.html',
        logado='usuario_id' in session, # Corrigido para verificar a sessão
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
            return redirect('/login')
        except sqlite3.IntegrityError:
            return render_template('cadastro.html', erro="Email já existe!")

    return render_template('cadastro.html')


@app.route('/prateleira', methods=['GET', 'POST'])
def produtos():
    if 'usuario_id' not in session:
        return redirect('/login')

    if not session.get('is_admin', False):
        return "Acesso negado! Você precisa ser administrador.", 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        tipo = request.form['tipo']
        tamanho = request.form.get('tamanho', '') # Tamanho padrão (apenas para a lista de produtos)
        quantidade = int(request.form['quantidade'])
        preco = int(float(request.form['preco'].replace(',', '.')) * 100)
        descricao = request.form.get('descricao', '') 
        tamanhos_disponiveis = request.form.get('tamanhos_disponiveis', 'PP,P,M,G,GG') 

        foto = request.files.get('foto')
        foto_filename = None
        if foto and foto.filename != '':
            foto_filename = secure_filename(foto.filename)
            foto.save(os.path.join(UPLOAD_FOLDER, foto_filename))

        cursor.execute(
            "INSERT INTO produtos (nome, tipo, tamanho, quantidade, preco, foto, descricao, tamanhos_disponiveis) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nome, tipo, tamanho, quantidade, preco, foto_filename, descricao, tamanhos_disponiveis)
        )
        conn.commit()

    cursor.execute("SELECT * FROM produtos ORDER BY produto_id DESC")
    produtos_lista = cursor.fetchall()

    return render_template('prateleira.html', produtos=produtos_lista)


@app.route("/remove_produto/<int:produto_id>", methods=['POST'])
def remove_produto(produto_id):
    if 'usuario_id' not in session or not session.get('is_admin', False):
        return "Acesso negado! Você precisa ser administrador.", 403

    conn = get_db()
    cursor = conn.cursor()
    # Remove as avaliações antes do produto para evitar erro de FK
    cursor.execute("DELETE FROM avaliacoes WHERE produto_id = ?", (produto_id,))
    cursor.execute("DELETE FROM produtos WHERE produto_id = ?", (produto_id,))
    conn.commit()

    return redirect('/prateleira')


@app.route('/carrinho')
def carrinho():
    if 'usuario_id' not in session:
        return redirect('/login')

    user_id = session['usuario_id']
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pega todos os itens do carrinho do usuário (CORREÇÃO: Buscando tamanho_selecionado)
    cur.execute('''
        SELECT c.id AS carrinho_id, c.usuario_id, c.produto_id, c.quantidade, c.preco, c.cupom,
               p.nome, p.foto, p.tipo, p.tamanho, c.tamanho_selecionado
        FROM carrinho c
        JOIN produtos p ON c.produto_id = p.produto_id
        WHERE c.usuario_id = ?
        ORDER BY c.id DESC
    ''', (user_id,))
    rows = cur.fetchall()

    itens = []
    total_cents = 0
    for r in rows:
        item = dict(r)
        item['preco_display'] = "{:.2f}".format(item['preco'] / 100.0)
        item['subtotal_display'] = "{:.2f}".format((item['preco'] * item['quantidade']) / 100.0)
        itens.append(item)
        total_cents += item['preco'] * item['quantidade']

    total_display = "{:.2f}".format(total_cents / 100.0)

    # Verifica se há cupom aplicado na sessão
    cupom_aplicado = session.get('cupom_aplicado')
    desconto = session.get('desconto', 0)
    total_desconto_display = None

    if desconto and total_cents > 0:
        total_com_desconto = total_cents * (1 - desconto)
        total_desconto_display = "{:.2f}".format(total_com_desconto / 100.0)

    mensagem_cupom = session.pop('mensagem_cupom', None)

    return render_template(
        'carrinho.html',
        itens=itens,
        total_display=total_display,
        total_desconto_display=total_desconto_display,
        cupom_aplicado=cupom_aplicado,
        mensagem_cupom=mensagem_cupom
    )

@app.route('/adicionar_ao_carrinho/<int:produto_id>', methods=['POST'])
def adicionar_ao_carrinho(produto_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    user_id = session['usuario_id']
    quantidade = int(request.form.get('quantidade', 1))
    if quantidade < 1:
        quantidade = 1
        
    tamanho_selecionado = request.form.get('tamanho_selecionado')
    if not tamanho_selecionado:
        # Se o tamanho não for selecionado, redireciona para a página do produto (CORREÇÃO)
        return redirect(f'/produto/{produto_id}')


    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT produto_id, preco FROM produtos WHERE produto_id = ?', (produto_id,))
    produto = cur.fetchone()
    if not produto:
        return "Produto não encontrado.", 404

    preco_cents = produto['preco']
    
    # CORREÇÃO CRÍTICA: Busca por produto_id E tamanho_selecionado para permitir
    # o mesmo produto em tamanhos diferentes como itens separados.
    cur.execute(
        'SELECT id, quantidade FROM carrinho WHERE usuario_id = ? AND produto_id = ? AND tamanho_selecionado = ?', 
        (user_id, produto_id, tamanho_selecionado)
    )
    existente = cur.fetchone()

    if existente:
        # Se o item do MESMO TAMANHO já existir, atualiza a quantidade.
        nova_qtd = existente['quantidade'] + quantidade
        cur.execute('UPDATE carrinho SET quantidade = ? WHERE id = ?', (nova_qtd, existente['id']))
    else:
        # Insere um novo item (com tamanho_selecionado)
        cur.execute(
            'INSERT INTO carrinho (usuario_id, produto_id, quantidade, preco, tamanho_selecionado) VALUES (?, ?, ?, ?, ?)',
            (user_id, produto_id, quantidade, preco_cents, tamanho_selecionado)
        )
    
    conn.commit()

    # Mantém o cupom ativo na sessão, mas sem recalcular aqui
    cupom_aplicado = session.get('cupom_aplicado')
    desconto = session.get('desconto', 0)

    # Nenhum cálculo de total_cents aqui
    return redirect('/carrinho')


@app.route('/remover_do_carrinho/<int:carrinho_id>', methods=['POST'])
def remover_do_carrinho(carrinho_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    user_id = session['usuario_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM carrinho WHERE id = ? AND usuario_id = ?', (carrinho_id, user_id))
    conn.commit()

    return redirect('/carrinho')


@app.route('/atualizar_carrinho/<int:carrinho_id>', methods=['POST'])
def atualizar_carrinho(carrinho_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    try:
        nova_qtd = int(request.form.get('quantidade', 1))
    except ValueError:
        nova_qtd = 1
    if nova_qtd < 1:
        nova_qtd = 1

    user_id = session['usuario_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE carrinho SET quantidade = ? WHERE id = ? AND usuario_id = ?', (nova_qtd, carrinho_id, user_id))
    conn.commit()

    return redirect('/carrinho')


@app.route('/aplicar_cupom', methods=['POST'])
def aplicar_cupom():
    if 'usuario_id' not in session:
        return redirect('/login')

    codigo_cupom = request.form.get('cupom', '').strip().upper()
    if not codigo_cupom:
        return redirect('/carrinho')

    user_id = session['usuario_id']
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Verifica se o cupom existe
    cur.execute('SELECT * FROM cupom WHERE UPPER(cupom) = ?', (codigo_cupom,))
    cupom = cur.fetchone()

    if not cupom:
        session['mensagem_cupom'] = "Cupom inválido!"
        return redirect('/carrinho')

    # Obtém o desconto (ex: 0.10 para 10%)
    desconto = float(cupom['desconto'])

    # Aplica o cupom a todos os itens do carrinho do usuário
    cur.execute('UPDATE carrinho SET cupom = ? WHERE usuario_id = ?', (codigo_cupom, user_id))
    conn.commit()

    # Salva o estado na sessão
    session['cupom_aplicado'] = codigo_cupom
    session['desconto'] = desconto
    session['mensagem_cupom'] = f"Cupom '{codigo_cupom}' aplicado! ({int(desconto * 100)}% de desconto)"

    return redirect('/carrinho')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


categoria= {
    "CALÇADOS": 1.2,
    "ACESSORIOS": 0.3,
    "CALÇA": 0.8,     
    "JAQUETA": 0.8,     
    "ROUPA": 0.8,     
    "DEFAULT": 0.8     
}

def get_peso_por_tipo(tipo_produto):
    tipo_normalizado = tipo_produto.upper().strip()
    
    # Mapeia tipos comuns de 'roupas' para a categoria principal
    if tipo_normalizado in ["CALÇA", "JAQUETA", "CAMISETA", "MOLETOM"]:
        return categoria["ROUPA"]
        
    # Retorna o peso se encontrado, senão usa o padrão
    return categoria.get(tipo_normalizado, categoria["DEFAULT"])

def obter_regiao(uf):
    regioes = {
        "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
        "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
        "Centro-Oeste": ["DF", "GO", "MT", "MS"],
        "Sudeste": ["ES", "MG", "RJ", "SP"],
        "Sul": ["PR", "RS", "SC"]
    }
    for regiao, estados in regioes.items():
        if uf in estados:
            return regiao
    return "Desconhecida"

def obter_fator(regiao):
    fatores = {
        "Sudeste": 1.0,
        "Sul": 1.1,
        "Centro-Oeste": 1.25,
        "Nordeste": 1.4,
        "Norte": 1.6,
        "Desconhecida": 1.8 # Fator padrão
    }
    return fatores.get(regiao, 1.8)


@app.route('/calcular_frete', methods=['POST'])
def calcular_frete_api():

    if 'usuario_id' not in session:
        return jsonify({"erro": "Usuário não logado"}), 401

    # Pega o CEP do formulário e limpa (remove não-dígitos)
    cep = request.form.get('cep', '')
    cep_limpo = ''.join(filter(str.isdigit, cep))

    if len(cep_limpo) != 8:
        return jsonify({"erro": "CEP inválido. Forneça 8 dígitos."}), 400

    user_id = session['usuario_id']
    conn = get_db()
    cur = conn.cursor()

    # 1. Buscar itens do carrinho e juntar com produtos para obter tipo, preco e quantidade
    cur.execute('''
        SELECT p.tipo, p.nome, c.quantidade, c.preco
        FROM carrinho c
        JOIN produtos p ON c.produto_id = p.produto_id
        WHERE c.usuario_id = ?
    ''', (user_id,))
    itens_carrinho = cur.fetchall()

    if not itens_carrinho:
        return jsonify({"erro": "Seu carrinho está vazio"}), 400

    # Calcula peso total e valor total (em centavos)
    peso_total_kg = 0.0
    valor_pedido_total_cents = 0

    for item in itens_carrinho:
        peso_item = get_peso_por_tipo(item['tipo'])
        peso_total_kg += peso_item * item['quantidade']
        valor_pedido_total_cents += item['preco'] * item['quantidade'] # Preço já está em centavos

    desconto = session.get('desconto', 0)
    if desconto > 0:
        valor_pedido_total_cents = int(valor_pedido_total_cents * (1 - desconto))
        
    try:
        res = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
        res.raise_for_status() # Lança exceção para erros HTTP (4xx, 5xx)
        dados_cep = res.json()
        
        if dados_cep.get('erro'):
            return jsonify({"erro": "CEP não encontrado"}), 404
            
    except requests.RequestException as e:
        print(f"Erro na API ViaCEP: {e}")
        return jsonify({"erro": "Não foi possível consultar o CEP. Tente novamente."}), 500

    uf = dados_cep.get('uf')
    regiao = obter_regiao(uf)
    fator = obter_fator(regiao)

    frete_cents = int((peso_total_kg * 5) * fator * 100)

    if valor_pedido_total_cents >= 15000:
        frete_cents = 0
        
    frete_gratis = (frete_cents == 0)

    resultado = {
        "cidade": dados_cep.get('localidade'),
        "uf": uf,
        "regiao": regiao,
        "cep": dados_cep.get('cep'),
        "peso_total_kg": round(peso_total_kg, 2),
        "valor_pedido_reais": round(valor_pedido_total_cents / 100.0, 2),
        "valor_frete_reais": round(frete_cents / 100.0, 2),
        "frete_gratis": frete_gratis,
        "mensagem_frete": "Grátis 🎉" if frete_gratis else f"R$ {round(frete_cents / 100.0, 2):.2f}",
        "cupom_aplicado": session.get('cupom_aplicado'),
        "desconto_aplicado": int(desconto * 100) if desconto > 0 else 0
    }

    return jsonify(resultado)

if __name__ == '__main__':
    # Garante que as tabelas estejam corretas e as colunas adicionais existam
    with app.app_context():
        init_db()
        # Adiciona um produto de exemplo se a tabela estiver vazia
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM produtos")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO produtos (nome, tipo, tamanho, quantidade, preco, foto, descricao, tamanhos_disponiveis) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "Bota Monolith Noir",
                "CALÇADOS",
                "40",
                10,
                39999, # R$ 399,99
                "bota-monolith.png", # Use um nome de arquivo de imagem existente ou um placeholder
                "A Bota Monolith é a peça-chave para um visual dark e moderno, construída com couro premium e sola tratorada robusta.",
                "35,36,37,38,39,40,41"
            ))
            db.commit()

    app.run(debug=True)
