# python01

Small Python helpers (public domain).

| Module | What it does |
|---|---|
| `rw_field_defn` | Column specs → CREATE / INSERT / UPDATE |
| `rw_database` | Abstract Database / Table / Row |
| `rw_sqlite` | sqlite3 backend + rowid first / next / prev |
| `rw_rpg` | RPG II-style control-break reports |
| `report3` | Example of using RPG |

Requires Python 3.10+ (`match`/`case`). No pip packages.

```bash
python3 rw_field_defn_test.py
python3 rw_database_test.py
python3 rw_sqlite_test.py
python3 rw_rpg_test.py
