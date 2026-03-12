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

### 3. `PortGuard` — neomezený rozsah portů

`port_guard.py:28-49`: `get_listening_socket` nemá horní limit portů. Pokud je spousta portů obsazených, bude zkoušet donekonečna (porty se incrementují po 2 od 19000). V extrémním případě přeteče přes 65535.

### 4. `drop_all_dbs` dropuje databáze po kolekcích, ne celé

`util.py:35-46`: `drop_all_dbs` iteruje databáze ale volá `drop_all_collections`, ne `client.drop_database()`. To znamená, že prázdné databáze zůstanou. Jméno funkce je tak mírně zavádějící.

### 5. `test_fork_safe_readme_example.py` — neaktualizován podle README

README byl přepsán na URI-based vzor, ale tento test stále používá starý `mongo_client_factory` / lambda vzor. Měly by být synchronizované.


Zastaralý kód / dead code
--------------------------

### 6. Kompatibilní wrappery pro pymongo < 3.6/3.7

`util.py:14-32`: `list_database_names()`, `list_collection_names()`, `count_documents()` — podpora pro pymongo < 3.6 a < 3.7. CI testuje minimum pymongo 3.13.0, `requires-python = ">=3.7"`. Tyto wrappery jsou mrtvý kód. Navíc `count_documents` zastíní builtin `filter`.

### 7. `patch_pymongo_periodic_executor` — otázka užitečnosti

`util.py:49-81`: Patch se nedá revertovat (zakomentovaný `pex._run = original_run`), pro pymongo >= 4.9 je disabled (AttributeError), a v kódu je TODO komentář o jeho odstranění (`instant_mongo.py:184`). Test ho skipuje pro pymongo > 4.9. Zvážit kompletní odstranění.

### 8. `mongodb_uri` backwards-compat property

`instant_mongo.py:219-223`: Existuje od verze 1.0.7. Changelog zmiňuje breaking changes — pokud už se lámou věci, je otázka jestli má smysl tento alias udržovat. Minimálně by mohl vydat `DeprecationWarning`.


Konfigurace / packaging
-----------------------

### 9. `requires-python = ">=3.7"` — příliš nízko

`pyproject.toml:10`: Python 3.7 je EOL od 2023-06. CI testuje minimum 3.9. Deklarovat 3.7 podporu bez testování je zavádějící. Doporučuji `>=3.9`.

### 10. `build-system` — setuptools, ale projekt používá uv

`pyproject.toml:1-3`: Build backend je stále setuptools. Pokud se přešlo na uv, stojí za zvážení přechod na modernější backend (hatchling, flit apod.), ale setuptools funguje dobře.

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
