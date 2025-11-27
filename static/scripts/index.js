const socket = io();

socket.on('connect', () => {
  console.log('✅ Conectado ao servidor Socket.IO!');
  socket.emit("carregar_produtos");
});

socket.on("open_modal", () => {
  openModal()
});

socket.on("change_page", (data) => {
  window.location.href = data.url
})

socket.on("renderizar_produtos", data => {
    const container = document.querySelector('.roupas-container');

    if (!container) {
        console.error("Container .roupas-container não encontrado!");
        return;
    }

    container.innerHTML = ""; // limpar antes de renderizar

    data.produtos.forEach(produto => {

        // Criar container principal
        const wrapper = document.createElement("div");
        wrapper.classList.add("clothe");

        // Título
        const title = document.createElement("h1");
        title.textContent = produto.nome;

        // Decoração
        const deco = document.createElement("div");
        deco.classList.add("decoration");

        // Card da imagem
        const card = document.createElement("div");
        card.classList.add("card");

        // Imagem
        const img = document.createElement("img");
        img.src = `/static/assets/${produto.foto}` || "/static/assets/default.png";  
        img.alt = produto.nome;

        // Ícone (se quiser renderizar)
        const icon = document.createElement("i");
        icon.className = "fa-regular fa-heart";
        icon.id = "icon-roupa";

        // Montar elementos
        card.appendChild(img);
        card.appendChild(icon);

        wrapper.appendChild(title);
        wrapper.appendChild(deco);
        wrapper.appendChild(card);

        container.appendChild(wrapper);
    });

    console.log("Renderização concluída:", data.produtos);
});


function loginCheck(url) {
  socket.emit('login_check', { 'url': url })
}

function openModal() {
  let div = document.querySelector(".modal");
  let fundo = document.querySelector(".overlay");
  let header = document.querySelector(".menu-container");
  let img = document.querySelector(".hero-image");
  let container = document.querySelector(".hero");
  let title = document.querySelector(".titleHero");
  let subtitles = document.querySelectorAll(".filter");

  subtitles.forEach((subtitle) => {
    subtitle.style.position = "static";
  });

  title.style.zIndex = "initial";
  title.style.mixBlendMode = "initial";
  container.style.position = "static";
  header.style.position = "static";
  header.style.isolation = "initial";
  img.style.position = "static";
  img.style.zIndex = "initial";

  div.classList.add("visible");
  fundo.classList.add("visible");
}

function closeModal() {
  let div = document.querySelector(".modal");
  let fundo = document.querySelector(".overlay");
  let header = document.querySelector(".menu-container");
  let img = document.querySelector(".hero-image");
  let container = document.querySelector(".hero");
  let title = document.querySelector(".titleHero");
  let subtitles = document.querySelectorAll(".filter");

  subtitles.forEach((subtitle) => {
    subtitle.style.position = "relative";
  });

  title.style.zIndex = "1";
  title.style.mixBlendMode = "darken";
  container.style.position = "relative";
  header.style.position = "sticky";
  header.style.isolation = "isolate";
  img.style.position = "absolute";
  img.style.zIndex = "2";

  div.classList.remove("visible");
  fundo.classList.remove("visible");
}

const erro = document.getElementById("erro-msg")?.dataset.erro === "true";

if (erro) {
  openModal()
}
