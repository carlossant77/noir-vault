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
  const containerNome = document.querySelector('.brand')

  containerNome.textContent = produto.nome
  console.log(produto)
}

document.addEventListener("DOMContentLoaded", (e) => {
  carregarProduto()
})