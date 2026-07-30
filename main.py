from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Depends, Form, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

import models
import const
from database import engine, get_db, Base
from auth_utils import hash_password, verify_password, generate_hex_id, generate_session_token
from test_bank import get_questions, score_test

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Физтех-репетитор")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- Вспомогательное: определение текущего пользователя ----------

def get_current_user(session_token: str = Cookie(default=None), db: DBSession = Depends(get_db)):
    if not session_token:
        return None
    sess = db.query(models.Session).filter(models.Session.token == session_token).first()
    if not sess:
        return None
    user = db.query(models.User).filter(models.User.id == sess.user_id).first()
    if user:
        apply_september_grade_bump(user, db)
    return user


def apply_september_grade_bump(user: models.User, db: DBSession):
    """Каждое 1 сентября класс школьника увеличивается на 1 (пока не выпустится)."""
    if user.edu_status != "school" or user.grade is None:
        return
    today = datetime.utcnow().date()
    last_bump_marker = f"_bump_{today.year}"
    # простое решение без отдельной таблицы: сравниваем год создания/последнего входа
    # с текущим годом после 1 сентября
    sept_this_year = datetime(today.year, 9, 1).date()
    if today >= sept_this_year and user.created_at.date() < sept_this_year:
        if user.grade < 11:
            user.grade += 1
            user.created_at = datetime.utcnow()  # сдвигаем "точку отсчёта", чтобы не прибавлять дважды
            db.commit()


def grade_to_tier(grade: int) -> int:
    if grade <= 4:
        return 1
    if grade <= 6:
        return 2
    if grade <= 8:
        return 3
    return 4


def common_ctx(request: Request, user):
    return {
        "request": request,
        "user": user,
        "SUBJECTS": const.SUBJECTS,
        "GRADE_TIERS": const.GRADE_TIERS,
        "QUALIFICATIONS": const.QUALIFICATIONS,
        "CURRENCY_NAME": const.CURRENCY_NAME,
        "GRADE_TIER_LABELS": const.GRADE_TIER_LABELS,
    }


# ---------------------------- Главная страница ----------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("index.html", common_ctx(request, user))


# ---------------------------- Авторизация ----------------------------

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/account", status_code=302)
    return templates.TemplateResponse("register.html", common_ctx(request, user))


@app.post("/register")
def register_submit(
    request: Request,
    full_name: str = Form(...),
    grade: str = Form(""),
    contact: str = Form(...),
    password: str = Form(...),
    db: DBSession = Depends(get_db),
):
    grade_val = int(grade) if grade.strip().isdigit() else None
    new_user = models.User(
        hex_id=generate_hex_id(),
        full_name=full_name.strip(),
        grade=grade_val,
        edu_status="school" if grade_val else "student",
        contact=contact.strip(),
        password_hash=hash_password(password),
        role="student",
        subject_balances={},
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = generate_session_token()
    db.add(models.Session(token=token, user_id=new_user.id))
    db.commit()

    resp = RedirectResponse("/become-tutor", status_code=302)
    resp.set_cookie("session_token", token, httponly=True, max_age=60 * 60 * 24 * 30)
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user), error: str = ""):
    if user:
        return RedirectResponse("/account", status_code=302)
    ctx = common_ctx(request, user)
    ctx["error"] = error
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login")
def login_submit(contact: str = Form(...), password: str = Form(...), db: DBSession = Depends(get_db)):
    user = db.query(models.User).filter(models.User.contact == contact.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=1", status_code=302)

    token = generate_session_token()
    db.add(models.Session(token=token, user_id=user.id))
    db.commit()

    resp = RedirectResponse("/account", status_code=302)
    resp.set_cookie("session_token", token, httponly=True, max_age=60 * 60 * 24 * 30)
    return resp


@app.get("/logout")
def logout(session_token: str = Cookie(default=None), db: DBSession = Depends(get_db)):
    if session_token:
        db.query(models.Session).filter(models.Session.token == session_token).delete()
        db.commit()
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp


# ---------------------------- Стать репетитором: тест ----------------------------

@app.get("/become-tutor", response_class=HTMLResponse)
def become_tutor_page(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    ctx = common_ctx(request, user)
    return templates.TemplateResponse("become_tutor.html", ctx)


@app.post("/become-tutor/start")
def become_tutor_start(
    request: Request,
    subject: str = Form(...),
    grade_tier: int = Form(...),
    qualification: str = Form(...),
    user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    # проверка правила "24 часа на пересдачу"
    last_attempt = (
        db.query(models.TestAttempt)
        .filter(
            models.TestAttempt.user_id == user.id,
            models.TestAttempt.subject == subject,
            models.TestAttempt.grade_tier == grade_tier,
            models.TestAttempt.qualification == qualification,
            models.TestAttempt.passed == False,  # noqa: E712
        )
        .order_by(models.TestAttempt.taken_at.desc())
        .first()
    )
    if last_attempt and datetime.utcnow() - last_attempt.taken_at < timedelta(hours=const.TEST_RETRY_HOURS):
        wait_until = last_attempt.taken_at + timedelta(hours=const.TEST_RETRY_HOURS)
        ctx = common_ctx(request, user)
        ctx["retry_blocked_until"] = wait_until
        return templates.TemplateResponse("become_tutor.html", ctx)

    questions = get_questions(subject, count=5)
    ctx = common_ctx(request, user)
    ctx.update({
        "subject": subject,
        "grade_tier": grade_tier,
        "qualification": qualification,
        "questions": questions,
    })
    return templates.TemplateResponse("test.html", ctx)


@app.post("/become-tutor/submit")
async def become_tutor_submit(
    request: Request,
    subject: str = Form(...),
    grade_tier: int = Form(...),
    qualification: str = Form(...),
    user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    # вопросы пришли обратно в скрытых полях q_correct_<i>, чтобы можно было проверить ответы
    answers = {}
    questions = []
    i = 0
    while f"q_text_{i}" in form:
        questions.append({
            "q": form[f"q_text_{i}"],
            "correct": int(form[f"q_correct_{i}"]),
        })
        selected = form.get(f"answer_{i}")
        if selected is not None:
            answers[str(i)] = selected
        i += 1

    score = score_test(questions, answers)
    passed = score >= const.TEST_PASS_THRESHOLD

    db.add(models.TestAttempt(
        user_id=user.id, subject=subject, grade_tier=grade_tier,
        qualification=qualification, score_percent=score, passed=passed,
    ))

    if passed:
        existing = (
            db.query(models.TutorSubject)
            .filter(models.TutorSubject.user_id == user.id, models.TutorSubject.subject == subject)
            .first()
        )
        if existing:
            existing.grade_tier_max = max(existing.grade_tier_max, grade_tier)
            quals = set(existing.qualifications or [])
            quals.add(qualification)
            existing.qualifications = list(quals)
            existing.last_test_at = datetime.utcnow()
        else:
            db.add(models.TutorSubject(
                user_id=user.id, subject=subject, grade_tier_max=grade_tier,
                qualifications=[qualification], last_test_at=datetime.utcnow(),
            ))
        user.role = "tutor"

    db.commit()

    ctx = common_ctx(request, user)
    ctx.update({"score": score, "passed": passed, "subject": subject})
    return templates.TemplateResponse("test_result.html", ctx)


# ---------------------------- Личный кабинет ----------------------------

@app.get("/account", response_class=HTMLResponse)
def account(request: Request, user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    ctx = common_ctx(request, user)
    if user.role == "tutor":
        ctx["calendar_entries"] = (
            db.query(models.CalendarEntry)
            .filter(models.CalendarEntry.tutor_id == user.id)
            .order_by(models.CalendarEntry.date)
            .all()
        )
        template = "profile_tutor.html"
    else:
        template = "profile_student.html"
    return templates.TemplateResponse(template, ctx)


@app.post("/account/update-grade")
def update_grade(grade: int = Form(...), user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    user.grade = grade
    db.commit()
    return RedirectResponse("/account", status_code=302)


@app.post("/account/wanted-subject")
def add_wanted_subject(subject: str = Form(...), user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    db.add(models.WantedSubject(user_id=user.id, subject=subject))
    db.commit()
    return RedirectResponse("/account", status_code=302)


@app.post("/account/tutor-profile")
def update_tutor_profile(
    subject: str = Form(...),
    achievements: str = Form(""),
    description: str = Form(""),
    price: int = Form(0),
    discount_note: str = Form(""),
    user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    ts = db.query(models.TutorSubject).filter(
        models.TutorSubject.user_id == user.id, models.TutorSubject.subject == subject
    ).first()
    if ts:
        ts.achievements = achievements
        ts.description = description
        ts.price = price
        ts.discount_note = discount_note
        db.commit()
    return RedirectResponse("/account", status_code=302)


@app.post("/account/calendar/add")
def add_calendar_entry(
    date: str = Form(...), time: str = Form(""), note: str = Form(...),
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    if not user or user.role != "tutor":
        return RedirectResponse("/login", status_code=302)
    db.add(models.CalendarEntry(tutor_id=user.id, date=date, time=time, note=note))
    db.commit()
    return RedirectResponse("/account", status_code=302)


@app.post("/account/announcement")
def add_announcement(
    subject: str = Form(...), grade_tier: int = Form(...), qualification: str = Form(...),
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    db.add(models.Announcement(
        student_id=user.id, subject=subject, grade_tier=grade_tier, qualification=qualification,
    ))
    db.commit()
    # В реальном продакшне здесь нужно отправить уведомления всем подходящим
    # репетиторам (email/push). В этом прототипе подходящие объявления просто
    # видны репетитору в его личном кабинете - см. функцию matching_announcements.
    return RedirectResponse("/account", status_code=302)


def matching_announcements(user: models.User, db: DBSession):
    if user.role != "tutor":
        return []
    results = []
    for ts in user.tutor_subjects:
        anns = db.query(models.Announcement).filter(
            models.Announcement.subject == ts.subject,
            models.Announcement.grade_tier <= ts.grade_tier_max,
        ).all()
        for a in anns:
            if a.qualification in (ts.qualifications or []):
                results.append(a)
    return results


# ---------------------------- Поиск репетитора ----------------------------

@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    subject: str = "",
    grade_tier: int = 0,
    qualification: str = "",
    user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    ctx = common_ctx(request, user)
    tutors = []
    if subject and grade_tier and qualification:
        query = db.query(models.TutorSubject).filter(
            models.TutorSubject.subject == subject,
            models.TutorSubject.grade_tier_max >= grade_tier,
        )
        for ts in query.all():
            if qualification in (ts.qualifications or []):
                tutors.append(ts)
    ctx.update({
        "tutors": tutors,
        "f_subject": subject,
        "f_grade_tier": grade_tier,
        "f_qualification": qualification,
        "searched": bool(subject and grade_tier and qualification),
    })
    return templates.TemplateResponse("search.html", ctx)


@app.get("/tutor/{tutor_subject_id}", response_class=HTMLResponse)
def tutor_detail(request: Request, tutor_subject_id: int, user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    ts = db.query(models.TutorSubject).filter(models.TutorSubject.id == tutor_subject_id).first()
    ctx = common_ctx(request, user)
    ctx["ts"] = ts
    return templates.TemplateResponse("tutor_detail.html", ctx)


# ---------------------------- Сообщения ----------------------------

@app.post("/message/send")
def send_message(
    recipient_id: int = Form(...), body: str = Form(...),
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    db.add(models.Message(sender_id=user.id, recipient_id=recipient_id, body=body))
    db.commit()
    return RedirectResponse(f"/messages/{recipient_id}", status_code=302)


@app.get("/messages/{other_id}", response_class=HTMLResponse)
def messages_thread(request: Request, other_id: int, user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    other = db.query(models.User).filter(models.User.id == other_id).first()
    thread = db.query(models.Message).filter(
        or_(
            (models.Message.sender_id == user.id) & (models.Message.recipient_id == other_id),
            (models.Message.sender_id == other_id) & (models.Message.recipient_id == user.id),
        )
    ).order_by(models.Message.created_at).all()
    ctx = common_ctx(request, user)
    ctx.update({"other": other, "thread": thread})
    return templates.TemplateResponse("messages.html", ctx)


# ---------------------------- Форум ----------------------------

@app.get("/forum", response_class=HTMLResponse)
def forum_page(
    request: Request, subject: str = "", grade_tier: int = 0,
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    query = db.query(models.ForumQuestion)
    if subject:
        query = query.filter(models.ForumQuestion.subject_tag == subject)
    if grade_tier:
        query = query.filter(models.ForumQuestion.grade_tag == grade_tier)
    questions = query.order_by(models.ForumQuestion.created_at.desc()).all()

    ctx = common_ctx(request, user)
    ctx.update({"questions": questions, "f_subject": subject, "f_grade_tier": grade_tier})
    return templates.TemplateResponse("forum.html", ctx)


@app.post("/forum/ask")
def forum_ask(
    subject_tag: str = Form(...), grade_tag: int = Form(0), title: str = Form(...), body: str = Form(...),
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    q = models.ForumQuestion(
        author_id=user.id, subject_tag=subject_tag,
        grade_tag=grade_tag or None, title=title, body=body,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return RedirectResponse(f"/forum/{q.id}", status_code=302)


@app.get("/forum/{question_id}", response_class=HTMLResponse)
def forum_question_detail(request: Request, question_id: int, user=Depends(get_current_user), db: DBSession = Depends(get_db)):
    question = db.query(models.ForumQuestion).filter(models.ForumQuestion.id == question_id).first()
    answers = db.query(models.ForumAnswer).filter(models.ForumAnswer.question_id == question_id).order_by(models.ForumAnswer.created_at).all()
    ctx = common_ctx(request, user)
    ctx.update({"question": question, "answers": answers})
    return templates.TemplateResponse("forum_question.html", ctx)


@app.post("/forum/{question_id}/answer")
def forum_answer(
    question_id: int, body: str = Form(...),
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    db.add(models.ForumAnswer(question_id=question_id, author_id=user.id, body=body))
    db.commit()
    return RedirectResponse(f"/forum/{question_id}", status_code=302)


@app.post("/forum/{question_id}/best/{answer_id}")
def forum_choose_best(
    question_id: int, answer_id: int,
    user=Depends(get_current_user), db: DBSession = Depends(get_db),
):
    question = db.query(models.ForumQuestion).filter(models.ForumQuestion.id == question_id).first()
    if not question or not user or question.author_id != user.id or question.best_answer_id:
        return RedirectResponse(f"/forum/{question_id}", status_code=302)

    answer = db.query(models.ForumAnswer).filter(models.ForumAnswer.id == answer_id).first()
    if not answer:
        return RedirectResponse(f"/forum/{question_id}", status_code=302)

    question.best_answer_id = answer_id

    # начисление баллов: у автора лучшего ответа прибавляется, у автора вопроса - отнимается
    asker = db.query(models.User).filter(models.User.id == question.author_id).first()
    responder = db.query(models.User).filter(models.User.id == answer.author_id).first()

    subj = question.subject_tag
    asker.subject_balances = {**(asker.subject_balances or {}), subj: (asker.subject_balances or {}).get(subj, 0) - const.BEST_ANSWER_REWARD}
    responder.subject_balances = {**(responder.subject_balances or {}), subj: (responder.subject_balances or {}).get(subj, 0) + const.BEST_ANSWER_REWARD}

    # проверка автоматического статуса репетитора через форум
    if responder.subject_balances.get(subj, 0) >= const.FORUM_TUTOR_THRESHOLD:
        existing = db.query(models.TutorSubject).filter(
            models.TutorSubject.user_id == responder.id, models.TutorSubject.subject == subj,
        ).first()
        if not existing:
            db.add(models.TutorSubject(
                user_id=responder.id, subject=subj, grade_tier_max=1,
                qualifications=["Подтягивание на 3"], via_forum=True,
            ))
            responder.role = "tutor"

    db.commit()
    return RedirectResponse(f"/forum/{question_id}", status_code=302)
