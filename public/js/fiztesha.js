(function () {
  var toggleBtn = document.getElementById('fiztesha-toggle');
  var panel = document.getElementById('fiztesha-panel');
  var closeBtn = document.getElementById('fiztesha-close');
  var avatarBtn = document.getElementById('fiztesha-avatar-btn');
  var avatarHeader = document.getElementById('fiztesha-avatar-header');
  var messagesEl = document.getElementById('fiztesha-messages');
  var form = document.getElementById('fiztesha-form');
  var input = document.getElementById('fiztesha-input');

  if (!toggleBtn || !panel) return;

  function moscowHour() {
    try {
      var parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Europe/Moscow',
        hour: 'numeric',
        hour12: false
      }).formatToParts(new Date());
      var hourPart = parts.find(function (p) { return p.type === 'hour'; });
      return hourPart ? parseInt(hourPart.value, 10) % 24 : new Date().getHours();
    } catch (e) {
      return new Date().getHours();
    }
  }

  function updateAvatar() {
    var hour = moscowHour();
    var isDay = hour >= 8 && hour < 20;
    var src = isDay ? '/images/fiztesha-day.jpg' : '/images/fiztesha-night.jpg';
    if (avatarBtn) avatarBtn.src = src;
    if (avatarHeader) avatarHeader.src = src;
  }
  updateAvatar();
  setInterval(updateAvatar, 5 * 60 * 1000);

  function openPanel() {
    panel.classList.remove('fiztesha-hidden');
    if (messagesEl.children.length === 0) {
      addMessage('bot', 'Привет! Я Физтеша — помогу подобрать репетитора. Расскажи, по какому предмету нужна помощь, для какого класса и с какой целью (подтянуть оценку, подготовиться к экзамену или к ВСОШ) — можно всё сразу одним сообщением.');
    }
    input.focus();
  }
  function closePanel() {
    panel.classList.add('fiztesha-hidden');
  }

  toggleBtn.addEventListener('click', function () {
    if (panel.classList.contains('fiztesha-hidden')) openPanel();
    else closePanel();
  });
  closeBtn.addEventListener('click', closePanel);

  function addMessage(who, text) {
    var row = document.createElement('div');
    row.className = 'fiztesha-msg fiztesha-msg-' + who;
    row.textContent = text;
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    addMessage('user', text);
    input.value = '';

    fetch('/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        addMessage('bot', data.reply || 'Извини, что-то пошло не так.');
      })
      .catch(function () {
        addMessage('bot', 'Не получилось связаться с сервером. Попробуй ещё раз.');
      });
  });
})();
