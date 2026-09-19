const { SUBJECTS, GRADES, GOALS } = require('./constants');

const SUBJECT_SYNONYMS = {
  'Математика (алгебра и геометрия)': ['математик', 'алгебр', 'геометр', 'матеша', 'матан'],
  'Информатика': ['информатик', 'информ', 'инфа', 'кодинг', 'программирование школьное'],
  'Окружающий мир': ['окружающий мир', 'окружающему миру'],
  'География': ['географ'],
  'Биология': ['биолог'],
  'Астрономия': ['астроном'],
  'Физика': ['физик'],
  'Химия': ['хими'],
  'История': ['истори'],
  'Обществознание': ['обществ', 'обществознан'],
  'Социология': ['социолог'],
  'Политология': ['политолог'],
  'Английский язык': ['англ', 'english'],
  'Немецкий язык': ['немецк', 'немецкому'],
  'Французский язык': ['французск'],
  'Китайский язык': ['китайск'],
  'Русский язык': ['русск', 'русскому'],
  'Литература': ['литератур'],
  'Робототехника': ['робототехник', 'роботех'],
  'Программирование': ['программир', 'кодить', 'кодинг', 'программист']
};

const GRADE_RANGES = {
  '1-4': [1, 4],
  '5-6': [5, 6],
  '7-8': [7, 8],
  '9-11': [9, 11]
};

const GOAL_SYNONYMS = {
  '3': ['на тройку', 'на 3', 'подтянуть', 'подтянуться', 'слабо понимаю', 'отстаю', 'база', 'с нуля'],
  '5': ['на пятерку', 'на 5', 'улучшить оценку', 'хочу лучше понимать', 'углубить'],
  'exam': ['экзамен', 'огэ', 'егэ', 'контрольн', 'зачет', 'зачёт', 'проверочн'],
  'vsosh': ['всош', 'олимпиад', 'олимпиаду', 'олимпиады']
};

function normalize(text) {
  return (text || '').toLowerCase().replace(/ё/g, 'е');
}

function extractSubject(text) {
  const t = normalize(text);
  for (const subject of SUBJECTS) {
    if (t.includes(normalize(subject))) return subject;
  }
  for (const [subject, words] of Object.entries(SUBJECT_SYNONYMS)) {
    if (words.some(w => t.includes(normalize(w)))) return subject;
  }
  return null;
}

function extractGrade(text) {
  const t = normalize(text);
  for (const bucket of GRADES) {
    if (t.includes(bucket.value)) return bucket.value;
  }
  const match = t.match(/(\d{1,2})\s*(?:-?[а-я]{0,3})?\s*класс/);
  const num = match ? parseInt(match[1], 10) : null;
  if (num) {
    for (const [bucket, [lo, hi]] of Object.entries(GRADE_RANGES)) {
      if (num >= lo && num <= hi) return bucket;
    }
  }
  return null;
}

function extractGoal(text) {
  const t = normalize(text);
  for (const goal of GOALS) {
    if (t.includes(normalize(goal.label))) return goal.value;
  }
  for (const [goal, words] of Object.entries(GOAL_SYNONYMS)) {
    if (words.some(w => t.includes(normalize(w)))) return goal;
  }
  return null;
}

function extractMaxPrice(text) {
  const t = normalize(text);
  const match = t.match(/(?:до|дешевле|не дороже|максимум)\s*(\d{2,5})/);
  return match ? parseInt(match[1], 10) : null;
}

function isReset(text) {
  const t = normalize(text).trim();
  return t === 'сброс' || t === 'сначала' || t === 'заново' || t === 'начать заново';
}

module.exports = { extractSubject, extractGrade, extractGoal, extractMaxPrice, isReset };
