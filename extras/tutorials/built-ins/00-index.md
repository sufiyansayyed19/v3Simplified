# Built-In & Library Functions — Complete Parameter-by-Parameter Reference

> **How this guide is organized:** Instead of cramming everything into one giant file, every topic is separated into its own focused Markdown file inside `extras/tutorials/built-ins/`.
>
> **Every single function, class, decorator, and method** has its own dedicated section with:
> 1. **Import Path** — exact Python import.
> 2. **Simple Explanation** — plain-English meaning + real-world analogy.
> 3. **Parameters Table** — every parameter, its type, default value, and what it actually does.
> 4. **Return Value** — what you get back.
> 5. **Real Example in `ParkingSimplified`** — how we call it in this codebase.

---

## Directory & Topics Map

| File | Topic | Functions, Classes & Decorators Covered |
| :--- | :--- | :--- |
| **[01-app-bootstrap-and-errors.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/01-app-bootstrap-and-errors.md)** | **Topic 1: App Bootstrap & Errors** | `FastAPI`, `@app.get`, `@asynccontextmanager`, `app.include_router`, `app.dependency_overrides`, `@app.exception_handler`, `RequestValidationError`, `HTTPException`, `JSONResponse` |
| **[02-service-infrastructure-and-security.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/02-service-infrastructure-and-security.md)** | **Topic 2: Service Core, Security & Logging** | `BaseSettings`, `SettingsConfigDict`, `APIRouter`, `Depends`, `Query`, `Header`, `Response`, `status`, `HTTPBearer`, `HTTPAuthorizationCredentials`, `jwt.encode`, `jwt.decode`, `jwt.PyJWTError`, `httpx.Client`, `httpx.HTTPError`, `logging.basicConfig`, `logging.getLogger` |
| **[03-schemas-and-validation.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/03-schemas-and-validation.md)** | **Topic 3: Schemas & Validation (Pydantic v2)** | `BaseModel`, `ConfigDict`, `Field`, `EmailStr`, `Literal`, `@field_validator`, `model_validate` |
| **[04-database-sqlalchemy-and-alembic.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/04-database-sqlalchemy-and-alembic.md)** | **Topic 4: Database, SQLAlchemy 2.0 & Alembic** | `create_engine`, `sessionmaker`, `DeclarativeBase`, `Session`, `Mapped`, `mapped_column`, `UUID`, `ForeignKey`, `relationship`, `select`, `delete`, `func.count`, `desc`, `and_`, `or_`, `joinedload`, `with_for_update`, `create_all`, `db.execute`, `db.get`, `db.add`, `db.add_all`, `db.commit`, `db.refresh`, `db.close`, `scalar_one`, `scalar_one_or_none`, `scalars().all()`, `engine_from_config`, `NullPool`, `context.*`, `op.create_table`, `op.drop_table`, `sa.text` |
| **[05-python-stdlib-builtins.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/05-python-stdlib-builtins.md)** | **Topic 5: Python Standard Library** | `uuid.uuid4`, `uuid.UUID`, `.hex`, `secrets.randbelow`, `datetime.now`, `datetime.combine`, `timedelta`, `timezone.utc`, `ZoneInfo`, `Decimal`, `ABC`, `@abstractmethod`, `@dataclass`, `re.compile`, `re.sub`, `Generator` |
| **[06-testing-and-concurrency.md](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/extras/tutorials/built-ins/06-testing-and-concurrency.md)** | **Topic 6: Testing & Concurrency** | `TestClient`, `@pytest.fixture`, `StaticPool`, `threading.Barrier`, `ThreadPoolExecutor`, `subprocess.Popen` |
