import os
import sqlite3
conn = sqlite3.connect('data/app.db')
c = conn.cursor()
c.execute("SELECT id, email FROM users LIMIT 1")
print('User:', c.fetchone())
c.execute("SELECT * FROM user_configs WHERE user_id = 1")
print('Config:', c.fetchone())
conn.close()
