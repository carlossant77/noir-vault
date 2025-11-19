const socket = io();

socket.on('connect', () => {
    console.log('✅ Conectado ao servidor Socket.IO!');
  });

let loginRealizado = false;

socket.on("login realizado", (data) => {
  loginRealizado = true;
  console.log(data)
});

function redirect(local) {
  if (local === "perfil.html") {
    if (loginRealizado === false) {
      return openModal();
    }
  }
  window.location.href = local;
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

document.addEventListener("scroll", () => {
  // Seleciona os elementos corretos
  const section2 = document.querySelector("#secao-de-busca"); // terceira section (ponto de ativação)
  const navLinks = document.querySelector("#link-menu");
  const navLinks2 = document.querySelector("#link-menu2");
  const navLinks3 = document.querySelector("#link-menu3");
  const navLinks4 = document.querySelector("#link-menu4");
  const menu = document.getElementById("menu");

  // Cria o observer
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          navLinks.classList.add("visible");
          navLinks2.classList.add("visible");
          navLinks3.classList.add("visible");
          navLinks4.classList.add("visible");
        } else {
          navLinks.classList.remove("visible");
          navLinks2.classList.remove("visible");
          navLinks3.classList.remove("visible");
          navLinks4.classList.remove("visible");
          menu.checked = false;
        }
      });
    },
    { threshold: 1 }
  ); // 10% visível já ativa

  // Observa a seção desejada
  observer.observe(section2);
});
