# Матрица доступа 10.4

real FastAPI router, real sessions, owned 10.2 PostgreSQL, new transaction verification

| Маршрут | Actor | Ожидание | Факт | Профиль/identity/membership/history без записи |
| --- | --- | --- | --- | --- |
| GET /users/{owner}/profile-summary | anonymous | 401 | 401 | да |
| GET /users/{owner} | anonymous | 401 | 401 | да |
| PATCH /users/{owner}/profile | anonymous | 401 | 401 | да |
| POST /users/agent/message | anonymous | 401 | 401 | да |
| POST /users/agent/profile/confirm | anonymous | 401 | 401 | да |
| GET /users/{owner}/profile-summary | forged | 401 | 401 | да |
| GET /users/{owner} | forged | 401 | 401 | да |
| PATCH /users/{owner}/profile | forged | 401 | 401 | да |
| POST /users/agent/message | forged | 401 | 401 | да |
| POST /users/agent/profile/confirm | forged | 401 | 401 | да |
| GET /users/{owner}/profile-summary | expired | 401 | 401 | да |
| GET /users/{owner} | expired | 401 | 401 | да |
| PATCH /users/{owner}/profile | expired | 401 | 401 | да |
| POST /users/agent/message | expired | 401 | 401 | да |
| POST /users/agent/profile/confirm | expired | 401 | 401 | да |
| GET /users/{owner}/profile-summary | same_org | 403 | 403 | да |
| GET /users/{owner} | same_org | 403 | 403 | да |
| PATCH /users/{owner}/profile | same_org | 403 | 403 | да |
| POST /users/agent/message | same_org | 403 | 403 | да |
| POST /users/agent/profile/confirm | same_org | 403 | 403 | да |
| GET /users/{owner}/profile-summary | other_tenant | 403 | 403 | да |
| GET /users/{owner} | other_tenant | 403 | 403 | да |
| PATCH /users/{owner}/profile | other_tenant | 403 | 403 | да |
| POST /users/agent/message | other_tenant | 403 | 403 | да |
| POST /users/agent/profile/confirm | other_tenant | 403 | 403 | да |
| GET /users/{owner}/profile-summary | org_admin | 403 | 403 | да |
| GET /users/{owner} | org_admin | 403 | 403 | да |
| PATCH /users/{owner}/profile | org_admin | 403 | 403 | да |
| POST /users/agent/message | org_admin | 403 | 403 | да |
| POST /users/agent/profile/confirm | org_admin | 403 | 403 | да |
| GET /users/{owner}/profile-summary | owner | 200 | 200 | да |
| PATCH /users/{owner}/profile | owner | 200 | 200 | разрешённая запись владельца |
| PATCH /users/{owner}/profile | owner | 200 | 200 | разрешённая запись владельца |
| PATCH /users/{owner}/profile | owner | 200 | 200 | да |
| PATCH /users/{owner}/profile | owner | 400 | 400 | да |
| PATCH /users/{owner}/profile | owner | 409 | 409 | да |
| PATCH /users/{owner}/profile | owner | 409 | 409 | да |
| PATCH /users/{owner}/profile | owner | 409 | 409 | да |
| PATCH /users/{owner}/profile | owner | 422 | 422 | да |
| POST /users/agent/profile/confirm | owner | 409 | 409 | да |
| POST /users/agent/message | owner | 403 | 403 | да |
| GET /users | owner | 403 | 403 | да |
| GET /users | org_admin | 200 | 200 | да |
| GET /users/3/profile-summary | org_admin | 403 | 403 | да |
| POST /users/agent/profile/confirm | owner | 200 | 200 | разрешённая запись владельца |
| POST /users/agent/message | owner | 200 | 200 | разрешённая запись владельца |
| GET /users/{owner}/profile-summary | owner | 401 | 401 | да |
| PATCH /users/{owner}/profile | owner | 401 | 401 | да |
| POST /users/agent/message | owner | 401 | 401 | да |
