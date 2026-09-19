const express = require('express');
const store = require('../db/store');
const { extractSubject, extractGrade, extractGoal, extractMaxPrice, isReset } = require('../config/nlp');
const { GRADES, GOALS } = require('../config/constants');

const router = express.Router();

function gradeLabel(value) {
  const g = GRADES.find(x => x.value === value);
  return g ? g.label : value;
}
function goalLabel(value) {
  const g = GOALS.find(x => x.value === value);
  return g ? g.label : value;
}

function emptySlots() {
  return { subject: null, grade: null, goal: null, maxPrice: null };
}

function findMatches(slots) {
  const data = store.load();
  const tutors = data.users.filter(u => u.isTutor && u.tutorProfile);

  const scored = tutors.map(t => {
    let score = 0;
    if (slots.subject && t.tutorProfile.subject === slots.subject) score += 3;
    if (slots.grade && Array.isArray(t.tutorProfile.grades) && t.tutorProfile.grades.includes(slots.grade)) score += 2;
    if (slots.goal && t.tutorProfile.category === slots.goal) score += 2;
    if (slots.maxPrice && t.tutorProfile.price) {
      const price = parseInt(String(t.tutorProfile.price).replace(/\D/g, ''), 10);
      if (!isNaN(price)) {
        if (price <= slots.maxPrice) score += 1;
        else score -= 2;
      }
    }
    return { tutor: t, score };
  });

  return scored
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(x => x.tutor);
}

router.post('/chat', (req, res) => {
  const message = (req.body && req.body.message) || '';

  if (isReset(message)) {
    req.session.fiztesha = emptySlots();
    return res.json({
      reply: 'Хорошо, начинаем заново. По какому предмету нужна помощь?',
      slots: req.session.fiztesha,
      results: []
    });
  }

  if (!req.session.fiztesha) {
    req.session.fiztesha = emptySlots();
  }
  const slots = req.session.fiztesha;

  const foundSubject = extractSubject(message);
  const foundGrade = extractGrade(message);
  const foundGoal = extractGoal(message);
  const foundPrice = extractMaxPrice(message);

  if (foundSubject) slots.subject = foundSubject;
  if (foundGrade) slots.grade = foundGrade;
  if (foundGoal) slots.goal = foundGoal;
  if (foundPrice) slots.maxPrice = foundPrice;

  req.session.fiztesha = slots;

  const missing = [];
  if (!slots.subject) missing.push('subject');
  if (!slots.grade) missing.push('grade');
  if (!slots.goal) missing.push('goal');

  if (missing.length > 0) {
    const prompts = {
      subject: 'По какому предмету нужна помощь?',
      grade: 'В каком ты классе (или для какого класса ищешь репетитора)?',
      goal: 'А какая цель — подтянуть на тройку, на пятёрку, подготовиться к экзаменам или к ВСОШ?'
    };
    const known = [];
    if (slots.subject) known.push(slots.subject);
    if (slots.grade) known.push(gradeLabel(slots.grade));
    if (slots.goal) known.push(goalLabel(slots.goal));

    const ack = known.length ? `Записала: ${known.join(', ')}. ` : '';
    return res.json({
      reply: ack + prompts[missing[0]],
      slots,
      results: []
    });
  }

  const matches = findMatches(slots);

  if (matches.length === 0) {
    return res.json({
      reply: `По запросу «${slots.subject}, ${gradeLabel(slots.grade)}, ${goalLabel(slots.goal)}»${slots.maxPrice ? `, до ${slots.maxPrice} ₽` : ''} пока никого не нашла. Могу поискать по другим критериям — просто напиши, что изменить, или напиши «сброс», чтобы начать заново.`,
      slots,
      results: []
    });
  }

  const lines = matches.map(t => {
    const price = t.tutorProfile.price ? `${t.tutorProfile.price} ₽` : 'цена не указана';
    return `• ${t.fio} — ${t.tutorProfile.subject}, ${t.tutorProfile.grades.map(gradeLabel).join('/')}, ${price}`;
  });

  return res.json({
    reply: `Нашла подходящих репетиторов:\n${lines.join('\n')}\n\nМожешь написать любому из них через «Найти репетитора» → карточку профиля, или уточни запрос (например, добавь «до 800 рублей»). Чтобы начать новый поиск — напиши «сброс».`,
    slots,
    results: matches.map(t => ({ id: t.id, fio: t.fio }))
  });
});

router.post('/reset', (req, res) => {
  req.session.fiztesha = emptySlots();
  res.json({ ok: true });
});

module.exports = router;
