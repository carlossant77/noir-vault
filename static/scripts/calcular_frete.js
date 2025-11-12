document.addEventListener('DOMContentLoaded', function () {

    // Encontra o formulário de frete
    const formFrete = document.getElementById('form-frete');

    // Se o formulário não existir na página, não faz nada
    if (!formFrete) {
        return;
    }

    // Adiciona o listener de 'submit' ao formulário
    formFrete.addEventListener('submit', async function (event) {
        // Previne o envio padrão do formulário
        event.preventDefault();

        const cepInput = document.getElementById('cep');
        const resultadoDiv = document.getElementById('resultado');

        // Pega o valor do CEP
        const cep = cepInput.value;

        // Mostra mensagem de carregamento
        resultadoDiv.style.color = 'black';
        resultadoDiv.innerHTML = "Calculando...";

        // Prepara os dados para enviar (necessário para o request.form['cep'] no Flask)
        const formData = new FormData();
        formData.append('cep', cep);

        try {
            // Faz a chamada 'fetch' para a rota do Flask
            const response = await fetch('/calcular_frete', {
                method: 'POST',
                body: formData
            });

            // Converte a resposta para JSON
            const data = await response.json();

            // Se o Flask retornou um erro (ex: CEP inválido, carrinho vazio)
            if (data.erro) {
                resultadoDiv.style.color = 'red';
                resultadoDiv.innerHTML = `<p>Erro: ${data.erro}</p>`;
            } else {
                // Se deu tudo certo, exibe os resultados
                resultadoDiv.style.color = 'green';
                resultadoDiv.innerHTML = `
                    <p><b>Cidade:</b> ${data.cidade} - ${data.uf} (Região: ${data.regiao})</p>
                    <p><b>Peso Total:</b> ${data.peso_total_kg} kg</p>
                    <p><b>Valor Pedido:</b> R$ ${data.valor_pedido_reais.toFixed(2)}</p>
                    <p><b>Frete:</b> ${data.mensagem_frete}</p>
                `;
            }

        } catch (error) {
            // Erro de rede ou falha na chamada
            console.error("Erro ao calcular frete:", error);
            resultadoDiv.style.color = 'red';
            resultadoDiv.innerHTML = "<p>Não foi possível calcular o frete. Tente novamente.</p>";
        }
    });
});
