import sqlite3
conn = sqlite3.connect('news.db')
cursor = conn.cursor()
try:
    cursor.execute('UPDATE user_profiles SET is_vip = 1, vip_expires_at = "2099-12-31T23:59:59"')
    conn.commit()
    print(f'Usuarios VIP actualizados: {cursor.rowcount}')
except Exception as e:
    print(f'Error: {e}')
conn.close()
