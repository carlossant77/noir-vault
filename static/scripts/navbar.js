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
    { threshold: 0.8 }
  ); // 10% visível já ativa

  // Observa a seção desejada
  observer.observe(section2);
});
