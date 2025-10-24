// Mostrar o banner de cookies após um pequeno delay
document.addEventListener("DOMContentLoaded", function () {
    setTimeout(function () {
      document.getElementById("cookieBanner").classList.add("show");
    }, 4000); // 1 segundo de delay
});

// Fechar o banner quando o botão for clicado
document.getElementById("acceptCookies").addEventListener("click", function () {
  document.getElementById("cookieBanner").classList.remove("show");
  setTimeout(function () {
    document.getElementById("cookieBanner").style.display = "none";
  }, 800); // Espera a animação terminar antes de esconder completamente
});