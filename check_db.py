import sqlite3
conn = sqlite3.connect('data/app.db')
c = conn.cursor()
c.execute("SELECT id, email FROM users WHERE email = '2762919805@qq.com'")
print('User:', c.fetchone())
c.execute("SELECT * FROM user_configs WHERE user_id = 1")
print('Config:', c.fetchone())
conn.close()
