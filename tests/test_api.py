"""Тесты API: студенты, дисциплины, оценки, ведомость, рейтинг."""


def grade(client, s, d, score):
    return client.post("/api/grades", json={"student_id": s["id"], "discipline_id": d["id"], "score": score})


def test_add_student(student):
    assert student["id"] > 0 and student["group_name"] == "CSE-22"


def test_student_validation(client):
    assert client.post("/api/students", json={"full_name": "A", "email": "bad", "group_name": "G"}).status_code == 400
    assert client.post("/api/students", json={"email": "a@b.kz", "group_name": "G"}).status_code == 400


def test_student_duplicate_email(client, student):
    r = client.post("/api/students", json={"full_name": "B", "email": "AIGERIM@example.com", "group_name": "G"})
    assert r.status_code == 409


def test_discipline_credits_validation(client):
    assert client.post("/api/disciplines", json={"title": "X", "credits": 0}).status_code == 400
    assert client.post("/api/disciplines", json={"title": "X", "credits": 11}).status_code == 400


def test_discipline_duplicate(client, disciplines):
    assert client.post("/api/disciplines", json={"title": "DevOps"}).status_code == 409


def test_grade_score_validation(client, student, disciplines):
    for bad in (-5, 101, "90", 90.5):
        assert grade(client, student, disciplines[0], bad).status_code == 400


def test_grade_unknown_student(client, disciplines):
    r = client.post("/api/grades", json={"student_id": 999, "discipline_id": disciplines[0]["id"], "score": 90})
    assert r.status_code == 404


def test_grade_letter_in_response(client, student, disciplines):
    g = grade(client, student, disciplines[0], 87).get_json()
    assert g["letter"] == "B+" and g["gpa"] == 3.33


def test_regrade_updates_not_duplicates(client, student, disciplines):
    grade(client, student, disciplines[0], 60)
    grade(client, student, disciplines[0], 90)
    t = client.get(f"/api/students/{student['id']}/transcript").get_json()
    assert len(t["grades"]) == 1 and t["grades"][0]["score"] == 90


def test_transcript_average_and_gpa(client, student, disciplines):
    grade(client, student, disciplines[0], 95)   # 5 кредитов, A = 4.0
    grade(client, student, disciplines[1], 72)   # 3 кредита, C+ = 2.33
    t = client.get(f"/api/students/{student['id']}/transcript").get_json()
    assert t["average_score"] == 83.5
    assert t["gpa"] == 3.37
    assert t["total_credits"] == 8


def test_transcript_without_grades(client, student):
    t = client.get(f"/api/students/{student['id']}/transcript").get_json()
    assert t["average_score"] is None and t["gpa"] is None


def test_discipline_report(client, disciplines):
    d = disciplines[0]
    for i, score in enumerate([95, 40, 75]):
        s = client.post("/api/students", json={"full_name": f"S{i}", "email": f"s{i}@ex.kz", "group_name": "G"}).get_json()
        grade(client, s, d, score)
    r = client.get(f"/api/disciplines/{d['id']}/report").get_json()
    assert r == {**r, "count": 3, "average_score": 70.0, "min": 40, "max": 95, "failed": 1}


def test_group_ranking_order(client, disciplines):
    names = {"Ахметов": 70, "Беков": 98, "Ержанова": 85}
    for i, (name, score) in enumerate(names.items()):
        s = client.post("/api/students", json={"full_name": name, "email": f"r{i}@ex.kz", "group_name": "CSE-22"}).get_json()
        grade(client, s, disciplines[0], score)
    ranking = client.get("/api/groups/CSE-22/ranking").get_json()
    assert [r["full_name"] for r in ranking] == ["Беков", "Ержанова", "Ахметов"]


def test_delete_student_removes_grades(client, student, disciplines):
    grade(client, student, disciplines[0], 80)
    assert client.delete(f"/api/students/{student['id']}").status_code == 204
    assert client.get(f"/api/students/{student['id']}").status_code == 404
    assert client.get("/api/stats").get_json()["grades"] == 0
