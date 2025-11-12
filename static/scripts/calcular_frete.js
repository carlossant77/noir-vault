const pesos = {
    roupas: 0.5,
    sneakers: 1.2,
    botas: 1.6,
    sapatos: 1.0,
    acessorios: 0.2
};

async function calcularFrete() {
    const categoria = document.getElementById('categoria').value;
    const quantidade = parseInt(document.getElementById('quantidade').value);
    const valorPedido = parseFloat(document.getElementById('valorPedido').value);
    const cep = document.getElementById('cep').value.replace(/\D/g, '');
    const resultado = document.getElementById('resultado');

    if (!categoria || isNaN(quantidade) || isNaN(valorPedido) || cep.length !== 8) {
        resultado.innerHTML = "Preencha todos os campos corretamente!";
        return;
    }

    try {
        const res = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const dados = await res.json();

        if (dados.erro) {
            resultado.innerHTML = "CEP não encontrado!";
            return;
        }

        const uf = dados.uf;
        const regiao = obterRegiao(uf);
        const fator = obterFator(regiao);

        const pesoTotal = pesos[categoria] * quantidade;
        let frete = (pesoTotal * 5) * fator;

        if (valorPedido >= 15000) {
            frete = 0;
        }

        resultado.innerHTML = `
          <p><b>Cidade:</b> ${dados.localidade} - ${uf}</p>
          <p><b>Região:</b> ${regiao}</p>
          <p><b>Categoria:</b> ${categoria.charAt(0).toUpperCase() + categoria.slice(1)}</p>
          <p><b>Quantidade:</b> ${quantidade}</p>
          <p><b>Peso total:</b> ${pesoTotal.toFixed(2)} kg</p>
          <p><b>Valor do pedido:</b> R$ ${valorPedido.toFixed(2)}</p>
          <p><b>Frete:</b> ${frete === 0 ? "Grátis 🎉" : "R$ " + frete.toFixed(2)}</p>
        `;
    } catch (error) {
        resultado.innerHTML = "Erro ao buscar o CEP!";
    }
}

function obterRegiao(uf) {
    const regioes = {
        "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
        "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
        "Centro-Oeste": ["DF", "GO", "MT", "MS"],
        "Sudeste": ["ES", "MG", "RJ", "SP"],
        "Sul": ["PR", "RS", "SC"]
    };
    for (const [regiao, estados] of Object.entries(regioes)) {
        if (estados.includes(uf)) return regiao;
    }
    return "Desconhecida";
}

function obterFator(regiao) {
    switch (regiao) {
        case "Sudeste": return 1.0;
        case "Sul": return 1.1;
        case "Centro-Oeste": return 1.25;
        case "Nordeste": return 1.4;
        case "Norte": return 1.6;
        default: return 1.8;
    }
}