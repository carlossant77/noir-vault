const wrap = document.querySelector('.carousel-wrap');
const carousel = document.querySelector('.carousel');
const slider = document.getElementById('track');

function updateSliderRange() {
  const visibleWidth = wrap.clientWidth;
  const totalWidth = carousel.scrollWidth;
  const maxTranslate = Math.max(0, totalWidth - visibleWidth);

  slider.max = Math.round(maxTranslate);
  slider.value = Math.min(Number(slider.value || 0), slider.max);

  carousel.style.transform = `translateX(-${slider.value}px)`;
}

slider.addEventListener('input', () => {
  carousel.style.transform = `translateX(-${slider.value}px)`;
});

window.addEventListener('resize', updateSliderRange);
window.addEventListener('load', updateSliderRange);