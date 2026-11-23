# Elo Saúde — MVP de contrarreferência

Plataforma MVP para a transição do cuidado entre Hospital/UPA e Atenção Primária (UBS), desenvolvida para o **Desafio 03 — Challenge CIS-AMFRI 2026**.

> O cuidado não termina na alta: a UBS recebe, confirma, agenda a visita domiciliar e o paciente é avisado (simulação via log/JSON).

Documentação técnica completa (arquitetura, ERD, diagrama de sequência e decisões de segurança): [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

---

## 1. Pré-requisitos

- Python **3.11+**
- PostgreSQL apenas se quiser rodar em modo produção (o MVP local usa SQLite)
- `pip` / `poetry` (opcional)

## 2. Instalação

Com **Poetry** (recomendado neste projeto):

```bash
cd "/home/henry-gabriel/Documents/Challenge CIS-AMFRI/Challenge-CIS-AMFRI/challenge"
poetry install
```

Alternativamente, com `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> O `.env` deste MVP já vem simulado. Para começar do zero: `cp .env.example .env`.

Variáveis principais em `.env`:

| Variável | Finalidade |
|---|---|
| `DATABASE_URL` | `sqlite:///./elo_saude.db` no MVP / `postgresql+psycopg://...` em produção |
| `SECRET_KEY` | assinatura dos JWTs |
| `ENCRYPTION_KEY` | chave Fernet para cifrar CPF, telefone, resumo e instruções |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | administrador criado no seed |
| `COOKIE_SECURE` | `true` em produção (HTTPS) |
| `CREATE_SCHEMA_ON_STARTUP` | `true` apenas no MVP local; em produção use Alembic |

## 3. Executar

```bash
poetry run task run
# equivalente: poetry run uvicorn challenge.app:app --reload --host 0.0.0.0 --port 8000
```

- Documentação interativa: <http://localhost:8000/docs>
- Telas HTML: <http://localhost:8000/ui/login>
- Health check: <http://localhost:8000/health>

Tasks disponíveis: `poetry run task --list` (`run`, `test`, `migrate`, `revision`).

### Usuários de demonstração (dados fictícios)

| Perfil | E-mail | Senha |
|---|---|---|
| Hospital | `hospital@elo.saude` | `Senha@123` |
| UPA | `upa@elo.saude` | `Senha@123` |
| UBS | `ubs@elo.saude` | `Senha@123` |
| Admin | valor de `ADMIN_EMAIL` no `.env` | valor de `ADMIN_PASSWORD` no `.env` |

Fluxo sugerido na interface: entre como **hospital**, registre a alta; entre como **UBS**, confirme o recebimento, agende a visita e clique em **Enviar aviso ao paciente** para ver a tela simulada do WhatsApp.

## 4. API

| Método | Endpoint | Perfil | Descrição |
|---|---|---|---|
| POST | `/api/auth/login` | qualquer | Login OAuth2 → JWT |
| POST | `/api/discharges/` | HOSPITAL | Registra alta, prescrições e plano de cuidados |
| GET | `/api/discharges/ubs/{ubs_id}` | UBS | Lista altas **pendentes** da UBS |
| PATCH | `/api/discharges/{id}/confirm` | UBS | Confirma recebimento |
| PATCH | `/api/discharges/{id}/schedule` | UBS | Agenda visita (data + período) |
| GET | `/api/discharges/{id}/notify-patient` | HOSPITAL/UBS | Simula WhatsApp e retorna a mensagem |

Estados: `PENDENTE → CONFIRMADA → AGENDADA → NOTIFICADA`. Transições inválidas retornam `409`.

## 5. Testes

```bash
poetry run task test
# equivalente: poetry run pytest -q
```

Os testes usam **SQLite em memória** (`sqlite:///:memory:`), sobrescrevem a dependência `get_session` e nunca conectam ao PostgreSQL.

## 6. Alembic (migrações)

Inicializar o Alembic (quando não houver estrutura ainda):

```bash
pip install alembic
alembic init alembic
# editar alembic.ini/env.py para usar DATABASE_URL e Base.metadata (já feito neste projeto)
```

Gerar uma migração automática a partir dos modelos e aplicar:

```bash
poetry run task revision -- "descreve a alteracao"
poetry run task migrate           # poetry run alembic upgrade head
poetry run alembic downgrade -1   # se precisar reverter
poetry run alembic current        # revisão atual
```

O exemplo incluído é `alembic/versions/0001_initial.py` (schema completo do MVP). Em produção:

```bash
export DATABASE_URL="postgresql+psycopg://usuario:senha@host:5432/elo_saude"
export CREATE_SCHEMA_ON_STARTUP=false
poetry run alembic upgrade head
```

## 7. Segurança e LGPD (resumo)

- Senhas com **Argon2id** (pwdlib); JWT HS256 com expiração.
- RBAC por perfil: hospital cria, UBS confirma/agenda; UBS só atua na sua unidade.
- CPF, telefone e textos clínicos **cifrados em repouso** (Fernet); CPF/telefone **mascarados** nas respostas.
- Trilha de auditoria em todas as transições e registro do aviso simulado.
- Apenas dados sintéticos; segredos fora do Git (`.env` ignorado).
- Limitações do MVP: sem refresh/revogação de token, sem envio real de WhatsApp e sem integração E-SUS/RNDS/FHIR.
