"""Бизнес-логика: студенты, дисциплины, оценки и расчёт среднего балла."""
import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Буквенная система оценивания (100-балльная шкала → буква → GPA)
GRADE_SCALE = [
    (95, "A", 4.0), (90, "A-", 3.67), (85, "B+", 3.33), (80, "B", 3.0),
    (75, "B-", 2.67), (70, "C+", 2.33), (65, "C", 2.0), (60, "C-", 1.67),
    (55, "D+", 1.33), (50, "D", 1.0), (0, "F", 0.0),
]


class ValidationError(Exception):
    """Некорректные входные данные (HTTP 400)."""


class NotFoundError(Exception):
    """Запись не найдена (HTTP 404)."""


class ConflictError(Exception):
    """Нарушение бизнес-правила (HTTP 409)."""


def _require(data, field):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"Поле '{field}' обязательно")
    return value.strip() if isinstance(value, str) else value


# ------------------------------------------------------------ расчёты
def letter_grade(score):
    """Перевод балла 0–100 в буквенную оценку и GPA."""
    if not isinstance(score, (int, float)) or not (0 <= score <= 100):
        raise ValidationError("Балл должен быть числом от 0 до 100")
    for minimum, letter, gpa in GRADE_SCALE:
        if score >= minimum:
            return letter, gpa


def average_score(scores):
    """Простой средний балл с округлением до 2 знаков; None, если оценок нет."""
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def weighted_gpa(items):
    """GPA, взвешенный по кредитам: sum(gpa * credits) / sum(credits).

    items — список пар (score, credits)."""
    total_credits = sum(c for _, c in items)
    if total_credits == 0:
        return None
    total = sum(letter_grade(s)[1] * c for s, c in items)
    return round(total / total_credits, 2)


# ---------------------------------------------------------- студенты
def add_student(db, data):
    full_name = _require(data, "full_name")
    email = _require(data, "email").lower()
    group = _require(data, "group_name")
    if not EMAIL_RE.match(email):
        raise ValidationError("Некорректный e-mail")
    with db.transaction() as cur:
        cur.execute("SELECT id FROM students WHERE email = %s", (email,))
        if cur.fetchone():
            raise ConflictError("Студент с таким e-mail уже зарегистрирован")
        sid = cur.insert(
            "INSERT INTO students (full_name, email, group_name) VALUES (%s, %s, %s)",
            (full_name, email, group),
        )
    return get_student(db, sid)


def get_student(db, student_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        row = cur.fetchone()
    if not row:
        raise NotFoundError(f"Студент {student_id} не найден")
    return _clean(row)


def list_students(db, group=None):
    sql, params = "SELECT * FROM students", ()
    if group:
        sql += " WHERE group_name = %s"
        params = (group,)
    with db.transaction() as cur:
        cur.execute(sql + " ORDER BY full_name", params)
        return [_clean(r) for r in cur.fetchall()]


def delete_student(db, student_id):
    get_student(db, student_id)
    with db.transaction() as cur:
        cur.execute("DELETE FROM grades WHERE student_id = %s", (student_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (student_id,))


# -------------------------------------------------------- дисциплины
def add_discipline(db, data):
    title = _require(data, "title")
    credits = data.get("credits", 5)
    if not isinstance(credits, int) or not (1 <= credits <= 10):
        raise ValidationError("Кредиты — целое число от 1 до 10")
    with db.transaction() as cur:
        cur.execute("SELECT id FROM disciplines WHERE title = %s", (title,))
        if cur.fetchone():
            raise ConflictError("Такая дисциплина уже существует")
        did = cur.insert("INSERT INTO disciplines (title, credits) VALUES (%s, %s)", (title, credits))
    return get_discipline(db, did)


def get_discipline(db, discipline_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM disciplines WHERE id = %s", (discipline_id,))
        row = cur.fetchone()
    if not row:
        raise NotFoundError(f"Дисциплина {discipline_id} не найдена")
    return _clean(row)


def list_disciplines(db):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM disciplines ORDER BY title")
        return [_clean(r) for r in cur.fetchall()]


# ------------------------------------------------------------ оценки
def set_grade(db, data):
    """Выставить или исправить оценку студента по дисциплине."""
    student_id = _require(data, "student_id")
    discipline_id = _require(data, "discipline_id")
    score = data.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not (0 <= score <= 100):
        raise ValidationError("Балл должен быть целым числом от 0 до 100")
    get_student(db, student_id)
    get_discipline(db, discipline_id)
    with db.transaction() as cur:
        cur.execute(
            "SELECT id FROM grades WHERE student_id = %s AND discipline_id = %s",
            (student_id, discipline_id),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE grades SET score = %s WHERE id = %s", (score, existing["id"]))
            gid = existing["id"]
        else:
            gid = cur.insert(
                "INSERT INTO grades (student_id, discipline_id, score) VALUES (%s, %s, %s)",
                (student_id, discipline_id, score),
            )
    return get_grade(db, gid)


def get_grade(db, grade_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM grades WHERE id = %s", (grade_id,))
        row = cur.fetchone()
    if not row:
        raise NotFoundError(f"Оценка {grade_id} не найдена")
    g = _clean(row)
    g["letter"], g["gpa"] = letter_grade(g["score"])
    return g


def student_transcript(db, student_id):
    """Ведомость студента: оценки, средний балл и GPA."""
    student = get_student(db, student_id)
    with db.transaction() as cur:
        cur.execute(
            "SELECT d.title, d.credits, g.score FROM grades g "
            "JOIN disciplines d ON d.id = g.discipline_id WHERE g.student_id = %s ORDER BY d.title",
            (student_id,),
        )
        rows = cur.fetchall()
    grades = []
    for r in rows:
        letter, gpa = letter_grade(r["score"])
        grades.append({"discipline": r["title"], "credits": r["credits"], "score": r["score"],
                       "letter": letter, "gpa": gpa})
    return {
        "student": student,
        "grades": grades,
        "average_score": average_score([g["score"] for g in grades]),
        "gpa": weighted_gpa([(g["score"], g["credits"]) for g in grades]),
        "total_credits": sum(g["credits"] for g in grades),
    }


def discipline_report(db, discipline_id):
    """Статистика по дисциплине: средний, минимальный и максимальный балл."""
    discipline = get_discipline(db, discipline_id)
    with db.transaction() as cur:
        cur.execute("SELECT score FROM grades WHERE discipline_id = %s", (discipline_id,))
        scores = [r["score"] for r in cur.fetchall()]
    return {
        "discipline": discipline,
        "count": len(scores),
        "average_score": average_score(scores),
        "min": min(scores) if scores else None,
        "max": max(scores) if scores else None,
        "failed": sum(1 for s in scores if s < 50),
    }


def group_ranking(db, group):
    """Рейтинг группы по GPA (по убыванию)."""
    result = []
    for s in list_students(db, group):
        t = student_transcript(db, s["id"])
        result.append({"student_id": s["id"], "full_name": s["full_name"],
                       "average_score": t["average_score"], "gpa": t["gpa"]})
    result.sort(key=lambda x: (x["gpa"] is None, -(x["gpa"] or 0), x["full_name"]))
    return result


def stats(db):
    with db.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM students")
        students = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM disciplines")
        disciplines = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n, AVG(score) AS avg FROM grades")
        g = cur.fetchone()
    avg = round(float(g["avg"]), 2) if g["avg"] is not None else 0
    return {"students": int(students), "disciplines": int(disciplines), "grades": int(g["n"]),
            "average_score": avg}


def _clean(row):
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in row.items()}
