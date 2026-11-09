from Api import routes
from Api.org_access import AdminScope


class Result:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class ModernDashboardConnection:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        if "COUNT(*) FILTER" in sql:
            return Result(one={"started": 3, "closed": 2})
        if "COUNT(DISTINCT cycle.id)" in sql:
            return Result(one={"ready": 1})
        if "WITH axis AS" in sql:
            return Result(many=[{"bucket_label": "08.11", "session_count": 2}])
        raise AssertionError(sql)


def test_admin_dashboard_uses_modern_cycles_and_has_honest_empty_skills():
    connection = ModernDashboardConnection()
    dashboard = routes._build_admin_dashboard(
        connection, AdminScope(is_superadmin=True, actor_user_id=7), "30d")

    metrics = {item.label: (item.value, item.delta) for item in dashboard.metrics}
    assert metrics == {
        "Готовых отчётов": ("1", "За всё время"),
        "Прохождение оценки": ("Завершено 2 из 3", "За всё время"),
    }
    assert dashboard.competency_average == []
    assert dashboard.insights[0].title == "Сводная оценка навыков пока недоступна"
    combined_sql = "\n".join(sql for sql, _params in connection.sql)
    assert "m5_cycles" in combined_sql
    assert "m8_reports" in combined_sql
    assert "collection_closed_at" in combined_sql
    assert "user_sessions" not in combined_sql


def test_admin_dashboard_zero_started_has_no_fake_percentage_or_score():
    connection = ModernDashboardConnection()

    def empty_execute(sql, params=()):
        connection.sql.append((sql, params))
        if "COUNT(*) FILTER" in sql:
            return Result(one={"started": 0, "closed": 0})
        if "COUNT(DISTINCT cycle.id)" in sql:
            return Result(one={"ready": 0})
        return Result(many=[])

    connection.execute = empty_execute
    dashboard = routes._build_admin_dashboard(connection, AdminScope(is_superadmin=True), "30d")
    values = " ".join(item.value for item in dashboard.metrics)
    labels = " ".join(item.label for item in dashboard.metrics)
    assert "Оценки ещё не начинались" in values
    assert "%" not in values
    assert "Средний индекс" not in labels
