from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Boolean, Text, JSON
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Уникальный шестнадцатеричный идентификатор.
    # По ТЗ пользователь его не видит - мы просто нигде не выводим это поле
    # в шаблонах, но оно всегда хранится в системе.
    hex_id = Column(String(16), unique=True, index=True, nullable=False)

    full_name = Column(String(255), nullable=False)

    # Для школьников - число 1..11. Для взрослых/студентов - None,
    # тогда используется edu_status + degree/education_profile.
    grade = Column(Integer, nullable=True)
    edu_status = Column(String(20), default="school")  # school / student / higher_ed
    degree = Column(String(255), nullable=True)              # научная степень (вручную)
    education_profile = Column(String(255), nullable=True)   # профиль обучения для взрослых

    contact = Column(String(255), nullable=False)  # email или телефон
    password_hash = Column(String(255), nullable=False)
    photo_url = Column(String(255), nullable=True)

    role = Column(String(20), default="student")  # student / tutor

    # Баллы формируются по каждому предмету отдельно: {"Физика": 40, "Химия": 10}
    subject_balances = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    tutor_subjects = relationship("TutorSubject", back_populates="user", cascade="all, delete-orphan")
    wanted_subjects = relationship("WantedSubject", back_populates="user", cascade="all, delete-orphan")


class TutorSubject(Base):
    """Один предмет, который пользователь преподаёт как репетитор."""
    __tablename__ = "tutor_subjects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    subject = Column(String(100), nullable=False)
    grade_tier_max = Column(Integer, nullable=False)  # 1..4, сдал за старшую ступень - открыты младшие
    qualifications = Column(JSON, default=list)       # список строк из const.QUALIFICATIONS

    achievements = Column(Text, nullable=True)   # по желанию
    description = Column(Text, nullable=True)    # по желанию
    price = Column(Integer, nullable=True)        # цена за занятие
    discount_note = Column(String(255), nullable=True)  # за что даётся скидка

    via_forum = Column(Boolean, default=False)  # стал репетитором через форум, а не через тест
    last_test_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tutor_subjects")


class WantedSubject(Base):
    """Предметы, по которым ученик ищет репетитора (для его личной страницы)."""
    __tablename__ = "wanted_subjects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)

    user = relationship("User", back_populates="wanted_subjects")


class TestAttempt(Base):
    """История попыток сдачи теста на статус репетитора."""
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    grade_tier = Column(Integer, nullable=False)
    qualification = Column(String(100), nullable=False)
    score_percent = Column(Integer, nullable=False)
    passed = Column(Boolean, nullable=False)
    taken_at = Column(DateTime, default=datetime.utcnow)


class ForumQuestion(Base):
    __tablename__ = "forum_questions"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_tag = Column(String(100), nullable=False)
    grade_tag = Column(Integer, nullable=True)  # ступень 1-4, необязательно
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    best_answer_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ForumAnswer(Base):
    __tablename__ = "forum_answers"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("forum_questions.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    """Объявление ученика: какого репетитора он ищет."""
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    grade_tier = Column(Integer, nullable=False)
    qualification = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    """Внутренняя переписка ученик <-> репетитор."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)


class CalendarEntry(Base):
    """Личный календарь репетитора: занятия и заметки."""
    __tablename__ = "calendar_entries"

    id = Column(Integer, primary_key=True)
    tutor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String(20), nullable=False)  # YYYY-MM-DD
    time = Column(String(20), nullable=True)   # HH:MM
    note = Column(Text, nullable=False)


class Session(Base):
    """Простая таблица сессий вместо тяжёлых внешних библиотек авторизации."""
    __tablename__ = "sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
