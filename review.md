Review celého projektu
======================

Celkový dojem
-------------

Projekt je přehledný, dobře strukturovaný a plní svůj účel. Kód je čitelný, testy pokrývají klíčové scénáře. Níže jsou konkrétní nálezy.


Bugy / potenciální problémy
----------------------------

### 1. ~~`raise e` místo `raise` — ztráta traceback kontextu~~ OPRAVENO

Opraveno na obou místech (`instant_mongo.py` i `test_basic_usage.py`) — `raise e` nahrazeno holým `raise`, které zachovává traceback chain.

### 2. ~~`_wait_for_accepting_tcp_conns` — chybí timeout~~ OPRAVENO

`_wait_for_accepting_tcp_conns` i `_init_rs` nyní používají `monotonic_ns()` s deadlinem odvozeným z `self.wait_timeout` (výchozí 10s). Po překročení timeoutu vyhodí `TimeoutError`.

### 3. ~~`PortGuard` — neomezený rozsah portů~~ OPRAVENO

Přidán wraparound — po dosažení portu 65535 se `_next_port` vrátí na `_start_port`. Rozsah ~23 000 párů portů je v praxi dostatečný.

### 4. ~~`drop_all_dbs` dropuje databáze po kolekcích, ne celé~~ OPRAVENO

`drop_all_dbs` nyní volá `client.drop_database()` místo `drop_all_collections()`. Databáze se mažou celé, prázdné databáze nezůstávají. `drop_all_collections` ponechána jako samostatná utilita.

### 5. ~~`test_fork_safe_readme_example.py` — neaktualizován podle README~~ OPRAVENO

Test přepsán na URI-based vzor odpovídající aktuálnímu README.


Zastaralý kód / dead code
--------------------------

### 6. ~~Kompatibilní wrappery pro pymongo < 3.6/3.7~~ PONECHÁNO

Wrappery ponechány záměrně.

### 7. ~~`patch_pymongo_periodic_executor` — otázka užitečnosti~~ OPRAVENO

Starý monkey-patch `_run` metody na třídě `PeriodicExecutor` odstraněn (nefungoval pro pymongo >= 4.9). Nahrazen jednodušším patchem konstanty `pymongo.common.MIN_HEARTBEAT_INTERVAL` (0.5 → 0.02) v `InstantMongoDB.start()`. Patch se aplikuje defenzivně — pouze pokud má konstanta očekávanou hodnotu.

### 8. ~~`mongodb_uri` backwards-compat property~~ OPRAVENO

Přidán `DeprecationWarning` s `stacklevel=2` při přístupu k `mongodb_uri`.


Konfigurace / packaging
-----------------------

### 9. ~~`requires-python = ">=3.7"` — příliš nízko~~ PONECHÁNO

Kód nepoužívá nic specifického pro 3.9+, zvýšení by zbytečně vyloučilo uživatele.

### 10. ~~`build-system` — setuptools, ale projekt používá uv~~ OPRAVENO

`pyproject.toml:1-3`: Build backend přepnut ze setuptools na hatchling.

### 11. Chybí `py.typed` marker a type annotations

Většina veřejných metod nemá type annotations (kromě `instant_mongo.py` kde jsou). `port_guard.py` a `util.py` nemají žádné.


Testy
-----

### 12. Duplikovaná `needs_mongod` fixture

`test_basic_usage.py:18` (scope=session) a `test_async_usage.py:16` (scope=module) — identická logika, liší se jen scope. Mohla by být v `conftest.py`.

### 13. Testy závisejí na pořadí

`test_fork_safe_readme_example.py`: `test_00_`, `test_01_`, `test_02_` — číslování naznačuje závislost na pořadí spouštění. S `pytest-randomly` by mohly failovat.

### 14. Async testy — chybí `needs_mongod` guard na úrovni testů

`test_async_usage.py`: `needs_mongod` je module-scoped fixture, ale je závislostí `instant_mongo` fixture, ne přímo testů. Pokud by se fixture přeuspořádaly, mohlo by dojít k chybě. Funguje, ale je to křehké.

### 15. Chybí test pro `follow_logs=True`

`OutputFileReader` (třída pro sledování logů mongod) nemá žádný dedikovaný test. Žádný existující test nespouští `InstantMongoDB` s `follow_logs=True`. Chyba v parsování výstupu nebo v thread lifecycle by prošla nepovšimnuta.

### 16. Chybí testy pro chybové stavy startu

Žádný test nepokrývá selhání startu mongod — např. chybějící binárka, nedostatečná práva na data dir, obsazený port. `MongoDBProcess.start()` a `InstantMongoDB.start()` mají error handling (cleanup přes `ExitStack`), ale ten není testovaný.


Drobnosti
---------

### 17. ~~`tcp_conns_accepted_on_port` — hardcoded errno~~ OPRAVENO

Nahrazeno `from errno import ECONNREFUSED` a porovnáním `e.errno != ECONNREFUSED`.

### 18. ~~`.format()` zůstal v `util.py:93`~~ OPRAVENO

Nahrazeno f-stringem pro konzistenci se zbytkem kódu.


Shrnutí priorit
---------------

| Priorita | Nález |
|----------|-------|
| ~~Vysoká~~ | ~~#2 chybějící timeout v `_wait_for_accepting_tcp_conns`~~ OPRAVENO |
| Střední | ~~#1 `raise e` → `raise`~~ OPRAVENO, #5 nesynchronizovaný fork-safe test, #15 chybí test pro `follow_logs`, #16 chybí testy pro chybové stavy startu |
| Nízká | #6 mrtvé compat wrappery, #7 periodic executor patch, #9 requires-python, #12 duplikovaná fixture |
| Kosmetika | #17 hardcoded errno, #18 zbylý `.format()` |
