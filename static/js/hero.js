document.addEventListener("DOMContentLoaded", () => {
  const stage = document.getElementById("hero-stage");
  const crest = document.getElementById("crest");
  if (!stage || !crest) return;

  let rotX = -18, rotY = 25;
  let dragging = false;
  let lastX = 0, lastY = 0;
  let autoSpin = true;

  function applyRotation() {
    crest.style.transform = `rotateX(${rotX}deg) rotateY(${rotY}deg)`;
  }
  applyRotation();

  function autoTick() {
    if (autoSpin && !dragging) {
      rotY += 0.25;
      applyRotation();
    }
    requestAnimationFrame(autoTick);
  }
  requestAnimationFrame(autoTick);

  stage.addEventListener("mousedown", (e) => {
    dragging = true;
    autoSpin = false;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  window.addEventListener("mouseup", () => { dragging = false; });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    rotY += dx * 0.5;
    rotX -= dy * 0.5;
    lastX = e.clientX;
    lastY = e.clientY;
    applyRotation();
  });

  stage.addEventListener("touchstart", (e) => {
    dragging = true;
    autoSpin = false;
    const t = e.touches[0];
    lastX = t.clientX; lastY = t.clientY;
  });
  stage.addEventListener("touchmove", (e) => {
    if (!dragging) return;
    const t = e.touches[0];
    const dx = t.clientX - lastX;
    const dy = t.clientY - lastY;
    rotY += dx * 0.5;
    rotX -= dy * 0.5;
    lastX = t.clientX; lastY = t.clientY;
    applyRotation();
    e.preventDefault();
  }, { passive: false });
  stage.addEventListener("touchend", () => { dragging = false; });
});
