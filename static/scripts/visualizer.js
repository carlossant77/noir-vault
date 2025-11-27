// Accordion behavior
document.querySelectorAll('.acc-item').forEach(item => {
  const btn = item.querySelector('.acc-header');
  const content = item.querySelector('.acc-content');

  btn.addEventListener('click', () => {
    if (item.classList.contains('active')) {
      item.classList.remove('active');
      content.style.maxHeight = null;
    } else {
      document.querySelectorAll('.acc-item').forEach(i => {
        i.classList.remove('active');
        i.querySelector('.acc-content').style.maxHeight = null;
      });
      item.classList.add('active');
      content.style.maxHeight = content.scrollHeight + "px";
    }
  });
});

function carregarProduto() {
  const produto = JSON.parse(localStorage.getItem("produtoSelecionado"));

  const fotoPrincipal = document.querySelector('.foto1')
  const foto2 = document.querySelector('.foto2')
  const foto3 = document.querySelector('.foto3')
  const foto4 = document.querySelector('.foto4')
  const containerNome = document.querySelector('.brand')
  const subtitle = document.querySelector('.subtitle')
  const price = document.querySelector('.price')
  const parcelas = document.querySelector('.installments')
  const opcao1 = document.querySelector('.option1')
  const opcao2 = document.querySelector('.option2')
  const opcao3 = document.querySelector('.option3')
  const opcao4 = document.querySelector('.option4')

  if (produto.tipo != 'Bota') {
    opcao1.textContent = 'PP'
    opcao2.textContent = 'P'
    opcao3.textContent = 'M'
    opcao4.textContent = 'G'
  }

  fotoPrincipal.src = '/static/assets/' + produto.fotos[0]
  foto2.src = '/static/assets/' + produto.fotos[1]
  foto3.src = '/static/assets/' + produto.fotos[2]
  foto4.src = '/static/assets/' + produto.fotos[3]
  containerNome.textContent = produto.nome
  subtitle.textContent = produto.nome
  price.textContent = 'R$' + produto.preco
  let valorParcela = produto.preco / 12
  parcelas.textContent = `12 x R$${valorParcela.toFixed(2)}`
  console.log(produto)
}

document.addEventListener("DOMContentLoaded", (e) => {
  carregarProduto()
})