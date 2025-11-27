from flask import Flask, request, redirect, session, render_template, g, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
import requests
import re
import json


app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "chave_secreta"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

UPLOAD_FOLDER = "static/assets"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@socketio.on("login_check")
def login_check(data):
    if session.get("usuario"):
        emit("change_page", {"url": data.get("url")})
    else:
        emit("open_modal")


@socketio.on("carregar_produtos")
def carregar_produtos():
    with sqlite3.connect("noir.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        produtos = cursor.execute("SELECT * FROM produtos").fetchall()

        resposta = []

        for p in produtos:
            fotos = cursor.execute(
                "SELECT caminho FROM fotos_produto WHERE produto_id = ? ORDER BY id ASC",
                (p["produto_id"],),
            ).fetchall()

            resposta.append(
                {
                    "produto_id": p["produto_id"],
                    "nome": p["nome"],
                    "preco": p["preco"],
                    "tipo": p["tipo"],
                    "quantidade": p["quantidade"],
                    "fotos": [f["caminho"] for f in fotos],  # lista das 4 imagens
                }
            )

        socketio.emit("renderizar_produtos", {"produtos": resposta})


@socketio.on("salvarFoto")
def salvar_foto(data):

    url = data.get("url")
    email = session.get("email")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
                    UPDATE usuarios 
                    SET foto = ? 
                    WHERE email = ?
                """,
        (url, email),
    )

    conn.commit()
    conn.close()

    session["foto"] = url


@socketio.on("adicionarCarrinho")
def salvar_carrinho(data):
    user_id = obter_user()
    adicionar_ao_carrinho(user_id, data)
    emit("abrir_confirmação", {"status": "sucesso"})


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("noir.db", timeout=30, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
        g.db.execute("PRAGMA busy_timeout = 30000;")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect("noir.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT UNIQUE,
            senha TEXT,
            foto TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """
    )

    cursor.execute(
        """
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
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            nota REAL NOT NULL, -- Nota de 0 a 5
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(produto_id),
            UNIQUE(usuario_id, produto_id) -- Garante apenas 1 avaliação por usuário/produto
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS carrinho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco REAL NOT NULL,
            cupom TEXT,
            tamanho_selecionado TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(produto_id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cupom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cupom TEXT UNIQUE,
            desconto REAL NOT NULL
        )
    """
    )

    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("SELECT descricao FROM produtos LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE produtos ADD COLUMN descricao TEXT")

    try:
        cursor.execute("SELECT tamanhos_disponiveis FROM produtos LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute(
            "ALTER TABLE produtos ADD COLUMN tamanhos_disponiveis TEXT DEFAULT 'PP,P,M,G,GG'"
        )

    try:
        cursor.execute("SELECT tamanho_selecionado FROM carrinho LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE carrinho ADD COLUMN tamanho_selecionado TEXT")

    conn.commit()
    conn.close()


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def get_media_avaliacao(produto_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT AVG(nota) as media, COUNT(nota) as total FROM avaliacoes WHERE produto_id = ?",
        (produto_id,),
    )
    resultado = cursor.fetchone()
    if resultado and resultado["total"] > 0:
        return round(resultado["media"], 1), resultado["total"]
    return 0.0, 0


@app.route("/avaliar_produto/<int:produto_id>", methods=["POST"])
def avaliar_produto(produto_id):
    if "usuario_id" not in session:
        return jsonify({"erro": "Você precisa estar logado para avaliar."}), 401

    try:
        # A nota vem como string do JS, ex: "3.5"
        nota_str = request.form.get("nota", "").strip()

        # 1. Validação do formato: 0 a 5, apenas .5 de casa decimal (ex: 1, 1.5, 2, 2.5, ..., 5)
        # O regex verifica se a string é:
        # - Um dígito de 0 a 4, opcionalmente seguido por .5 (ex: "3.5", "4")
        # - Ou exatamente 5 (ex: "5")
        if not nota_str or not re.fullmatch(r"([0-4](\.5)?)|5", nota_str):
            return (
                jsonify(
                    {
                        "erro": "Nota inválida. Use valores de 0 a 5, com incrementos de 0.5 (ex: 1, 1.5, 3.5)."
                    }
                ),
                400,
            )

        nota = float(nota_str)

        # 2. Validação do valor (redundante, mas seguro)
        if not (0.0 <= nota <= 5.0):
            return jsonify({"erro": "Nota deve estar entre 0 e 5."}), 400

    except ValueError:
        return jsonify({"erro": "Formato de nota inválido."}), 400

    usuario_id = session["usuario_id"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Usamos INSERT OR REPLACE para garantir que cada usuário só tenha uma avaliação por produto
        cursor.execute(
            "INSERT OR REPLACE INTO avaliacoes (usuario_id, produto_id, nota) VALUES (?, ?, ?)",
            (usuario_id, produto_id, nota),
        )
        conn.commit()

        # Recalcula a média após a inserção/atualização
        media_nova, total_avaliacoes_novo = get_media_avaliacao(produto_id)

        return jsonify(
            {
                "sucesso": True,
                "mensagem": "Avaliação salva com sucesso!",
                "media_avaliacao": media_nova,
                "total_avaliacoes": total_avaliacoes_novo,
            }
        )

    except Exception as e:
        print(f"Erro ao salvar avaliação: {e}")
        return jsonify({"erro": "Erro interno ao salvar a avaliação."}), 500


@app.route("/")
def home():

    return render_template(
        "index.html",
        logado=True,
        usuario=session["usuario"] if "usuario" in session else None,
        is_admin=session.get("is_admin", False),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nome, email, is_admin FROM usuarios WHERE email = ? AND senha = ?",
            (email, hash_senha(senha)),
        )
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            session["usuario_id"] = usuario["id"]
            session["usuario"] = usuario["nome"]
            session["email"] = email
            session["is_admin"] = bool(usuario["is_admin"])
            return redirect("/")
        else:
            return render_template("login.html", erro="Email ou senha incorretos!")

    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["username"]
        email = request.form["email"]
        senha = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)",
                (nome, email, hash_senha(senha)),
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("cadastro.html", erro="Email já existe!")

    return render_template("cadastro.html")


@app.route("/visualizar", methods=["GET", "POST"])
def visualizar():
    return render_template("visualizer.html")


def adicionar_ao_carrinho(cliente_id, produto):
    conn = get_db()
    cursor = conn.cursor()

    dados_json = json.dumps(produto)
    dados = produto["produto"]
    tamanho = produto["tamanho"]

    cursor.execute(
        """
        INSERT INTO carrinho (cliente_id, produto_id, dados_produto, tamanho_selecionado)
        VALUES (?, ?, ?, ?)
    """,
        (cliente_id, dados["produto_id"], dados_json, tamanho),
    )

    conn.commit()
    conn.close()


def obter_carrinho():
    user_id = obter_user()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
                   SELECT * FROM carrinho WHERE cliente_id = ?""",
        (user_id,),
    )
    
    colunas = cursor.fetchall()
    carrinho = [dict(row) for row in colunas]
        
    return carrinho


def obter_user():
    conn = get_db()
    cursor = conn.cursor()

    email = session.get("email")

    cursor.execute(
        """SELECT id FROM usuarios WHERE email = ?
                   """,
        (email,),
    )
    row = cursor.fetchone()
    user_id = row[0]
    return user_id

def calcular_compra():
    carrinho_bruto = obter_carrinho()
    
    carrinho = []
    for item in carrinho_bruto:
        dados_produto_dict = json.loads(item['dados_produto']) 
    
        item['produto_info'] = dados_produto_dict['produto']
    
        del item['dados_produto'] 
    
        carrinho.append(item)
    
    valor_compra = 0
    for item in carrinho:
        valor_item = item['produto_info']['preco']
        valor_compra += valor_item
        
    return valor_compra
    
@app.route("/carrinho", methods=["GET", "POST"])
def carrinho():
    carrinho_bruto = obter_carrinho()
    
    carrinho = []
    for item in carrinho_bruto:
        dados_produto_dict = json.loads(item['dados_produto']) 
    
        item['produto_info'] = dados_produto_dict['produto']
    
        del item['dados_produto'] 
    
        carrinho.append(item)
    
    valor_compra = calcular_compra()  
    return render_template("bag.html", carrinho=carrinho, valor_compra=valor_compra)


@app.route("/prateleira", methods=["GET", "POST"])
def prateleira():
    if "usuario_id" not in session:
        return redirect("/login")

    if not session.get("is_admin", False):
        return "Acesso negado! Você precisa ser administrador.", 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        tipo = request.form["tipo"]
        tamanho = request.form.get(
            "tamanho", ""
        )  # Tamanho padrão (apenas para a lista de produtos)
        quantidade = int(request.form["quantidade"])
        preco = int(float(request.form["preco"].replace(",", ".")) * 100)
        descricao = request.form.get("descricao", "")
        tamanhos_disponiveis = request.form.get("tamanhos_disponiveis", "PP,P,M,G,GG")

        foto = request.files.get("foto")
        foto_filename = None
        if foto and foto.filename != "":
            foto_filename = secure_filename(foto.filename)
            foto.save(os.path.join(UPLOAD_FOLDER, foto_filename))

        cursor.execute(
            "INSERT INTO produtos (nome, tipo, tamanho, quantidade, preco, foto, descricao, tamanhos_disponiveis) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                nome,
                tipo,
                tamanho,
                quantidade,
                preco,
                foto_filename,
                descricao,
                tamanhos_disponiveis,
            ),
        )
        conn.commit()

    cursor.execute("SELECT * FROM produtos ORDER BY produto_id DESC")
    cursor.execute("SELECT DISTINCT tipo FROM produtos")
    tipos = [row["tipo"] for row in cursor.fetchall()]
    produtos_lista = cursor.fetchall()
    conn.close()

    return render_template("prateleira.html", produtos=produtos_lista, tipos=tipos)


@app.route("/produtos", methods=["GET", "POST"])
def produtos():
    if "usuario_id" not in session:
        return redirect("/login")

    if not session.get("is_admin", False):
        return "Acesso negado! Você precisa ser administrador.", 403

    conn = get_db()

    with sqlite3.connect("noir.db", timeout=10, check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- SE FOR POST: inserção ---
        if request.method == "POST":
            nome_bruto = request.form["nome"]
            tipo_bruto = request.form["tipo"]
            tamanho = request.form.get("tamanho", "")
            quantidade = int(request.form["quantidade"])
            preco = int(float(request.form["preco"].replace(",", ".")) * 100)

            nome = nome_bruto.upper()
            tipo = tipo_bruto.upper()

            cursor.execute(
                """
                INSERT INTO produtos (nome, tipo, tamanho, quantidade, preco)
                VALUES (?, ?, ?, ?, ?)
            """,
                (nome, tipo, tamanho, quantidade, preco),
            )

            produto_id = cursor.lastrowid

            foto1 = request.files.get("foto1")
            foto2 = request.files.get("foto2")
            foto3 = request.files.get("foto3")
            foto4 = request.files.get("foto4")
            fotos = [foto1, foto2, foto3, foto4]

            for foto in fotos:
                if foto.filename != "":
                    foto_filename = secure_filename(foto.filename)
                    foto.save(os.path.join(UPLOAD_FOLDER, foto_filename))

                    cursor.execute(
                        """
                    INSERT INTO fotos_produto (produto_id, caminho)
                    VALUES (?, ?)
                    """,
                        (produto_id, foto_filename),
                    )

            conn.commit()

        # --- SEMPRE: buscar lista ---
        cursor.execute("SELECT * FROM produtos ORDER BY produto_id DESC")
        produtos_lista = cursor.fetchall()

    return render_template("prateleira.html", produtos=produtos_lista)


@app.route("/perfil")
def perfil():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT foto FROM usuarios WHERE email = ?", (session.get("email"),))
    url = cursor.fetchone()

    return render_template(
        "perfil.html",
        usuario=session.get("usuario"),
        email=session.get("email"),
        foto=url if url != "" or None else None,
    )


@app.route("/wishlist")
def wishlist():
    return render_template("wishlist.html")


@app.route("/aplicar_cupom", methods=["POST"])
def aplicar_cupom():
    if "usuario_id" not in session:
        return redirect("/login")

    codigo_cupom = request.form.get("cupom", "").strip().upper()
    if not codigo_cupom:
        return redirect("/carrinho")

    user_id = session["usuario_id"]
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Verifica se o cupom existe
    cur.execute("SELECT * FROM cupom WHERE UPPER(cupom) = ?", (codigo_cupom,))
    cupom = cur.fetchone()

    if not cupom:
        session["mensagem_cupom"] = "Cupom inválido!"
        return redirect("/carrinho")

    # Obtém o desconto (ex: 0.10 para 10%)
    desconto = float(cupom["desconto"])

    # Aplica o cupom a todos os itens do carrinho do usuário
    cur.execute(
        "UPDATE carrinho SET cupom = ? WHERE usuario_id = ?", (codigo_cupom, user_id)
    )
    conn.commit()

    # Salva o estado na sessão
    session["cupom_aplicado"] = codigo_cupom
    session["desconto"] = desconto
    session["mensagem_cupom"] = (
        f"Cupom '{codigo_cupom}' aplicado! ({int(desconto * 100)}% de desconto)"
    )

    return redirect("/carrinho")


categoria = {
    "CALÇADOS": 1.2,
    "ACESSORIOS": 0.3,
    "CALÇA": 0.8,
    "JAQUETA": 0.8,
    "ROUPA": 0.8,
    "DEFAULT": 0.8,
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
        "Sul": ["PR", "RS", "SC"],
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
        "Desconhecida": 1.8,  # Fator padrão
    }
    return fatores.get(regiao, 1.8)


@app.route("/calcular_frete", methods=["POST"])
def calcular_frete_api():
    if "usuario_id" not in session:
        return jsonify({"erro": "Usuário não logado"}), 401

    # Pega o CEP do formulário e limpa (remove não-dígitos)
    cep = request.form.get("cep", "")
    cep_limpo = "".join(filter(str.isdigit, cep))

    if len(cep_limpo) != 8:
        return jsonify({"erro": "CEP inválido. Forneça 8 dígitos."}), 400

    user_id = session["usuario_id"]
    conn = get_db()
    cur = conn.cursor()

    # 1. Buscar itens do carrinho e juntar com produtos para obter tipo, preco e quantidade
    cur.execute(
        """
        SELECT p.tipo, p.nome, c.quantidade, c.preco
        FROM carrinho c
        JOIN produtos p ON c.produto_id = p.produto_id
        WHERE c.usuario_id = ?
    """,
        (user_id,),
    )
    itens_carrinho = cur.fetchall()

    if not itens_carrinho:
        return jsonify({"erro": "Seu carrinho está vazio"}), 400

    # Calcula peso total e valor total (em centavos)
    peso_total_kg = 0.0
    valor_pedido_total_cents = 0

    for item in itens_carrinho:
        peso_item = get_peso_por_tipo(item["tipo"])
        peso_total_kg += peso_item * item["quantidade"]
        valor_pedido_total_cents += int(item["preco"]) * int(
            item["quantidade"]
        )  # Preço já está em centavos

    desconto = session.get("desconto", 0)
    if desconto > 0:
        valor_pedido_total_cents = int(valor_pedido_total_cents * (1 - desconto))

    try:
        res = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
        res.raise_for_status()  # Lança exceção para erros HTTP (4xx, 5xx)
        dados_cep = res.json()

        if dados_cep.get("erro"):
            return jsonify({"erro": "CEP não encontrado"}), 404

    except requests.RequestException as e:
        print(f"Erro na API ViaCEP: {e}")
        return (
            jsonify({"erro": "Não foi possível consultar o CEP. Tente novamente."}),
            500,
        )

    uf = dados_cep.get("uf")
    regiao = obter_regiao(uf)
    fator = obter_fator(regiao)

    frete_cents = int((peso_total_kg * 5) * fator * 100)

    if valor_pedido_total_cents >= 15000:
        frete_cents = 0

    frete_gratis = frete_cents == 0

    resultado = {
        "cidade": dados_cep.get("localidade"),
        "uf": uf,
        "regiao": regiao,
        "cep": dados_cep.get("cep"),
        "peso_total_kg": round(peso_total_kg, 2),
        "valor_pedido_reais": round(valor_pedido_total_cents / 100.0, 2),
        "valor_frete_reais": round(frete_cents / 100.0, 2),
        "frete_gratis": frete_gratis,
        "mensagem_frete": (
            "Grátis 🎉" if frete_gratis else f"R$ {round(frete_cents / 100.0, 2):.2f}"
        ),
        "cupom_aplicado": session.get("cupom_aplicado"),
        "desconto_aplicado": int(desconto * 100) if desconto > 0 else 0,
    }

    return jsonify(resultado)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
    socketio.run(app, debug=True)
