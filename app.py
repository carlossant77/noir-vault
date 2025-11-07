@app.route('/adicionar_ao_carrinho/<int:produto_id>', methods=['POST'])
def adicionar_ao_carrinho(produto_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    user_id = session['usuario_id']
    quantidade = int(request.form.get('quantidade', 1))
    if quantidade < 1:
        quantidade = 1

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT produto_id, preco FROM produtos WHERE produto_id = ?', (produto_id,))
    produto = cur.fetchone()
    if not produto:
        return "Produto não encontrado.", 404

    preco_cents = produto['preco']
    cur.execute('SELECT id, quantidade FROM carrinho WHERE usuario_id = ? AND produto_id = ?', (user_id, produto_id))
    existente = cur.fetchone()

    if existente:
        nova_qtd = existente['quantidade'] + quantidade
        cur.execute('UPDATE carrinho SET quantidade = ? WHERE id = ?', (nova_qtd, existente['id']))
    else:
        cur.execute(
            'INSERT INTO carrinho (usuario_id, produto_id, quantidade, preco) VALUES (?, ?, ?, ?)',
            (user_id, produto_id, quantidade, preco_cents)
        )
    conn.commit()

    # Mantém o cupom ativo na sessão, mas sem recalcular aqui
    cupom_aplicado = session.get('cupom_aplicado')
    desconto = session.get('desconto', 0)

    # Nenhum cálculo de total_cents aqui
    return redirect('/carrinho')
