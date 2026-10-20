
import sqlite3

DB_NAME = "fitness.db"


def create_table():
    connection = sqlite3.connect(DB_NAME)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS fitness_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            goal TEXT,
            level TEXT,
            steps INTEGER,
            workout_minutes INTEGER,
            weight REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def save_record(name, age, goal, level, steps,
                workout_minutes, weight):
    connection = sqlite3.connect(DB_NAME)

    connection.execute("""
        INSERT INTO fitness_records
        (name, age, goal, level, steps, workout_minutes, weight)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, age, goal, level, steps,
          workout_minutes, weight))

    connection.commit()
    connection.close()


def get_records():
    connection = sqlite3.connect(DB_NAME)

    records = connection.execute("""
        SELECT id, name, goal, steps, workout_minutes,
               weight, created_at
        FROM fitness_records
        ORDER BY id DESC
    """).fetchall()

    connection.close()
    return records


create_table()
