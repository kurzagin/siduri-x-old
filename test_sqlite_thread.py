import sqlite3
import threading

conn = sqlite3.connect(":memory:")

def do_query():
    try:
        conn.execute("SELECT 1")
    except Exception as e:
        print(f"Exception in thread: {type(e).__name__}: {e}")

t = threading.Thread(target=do_query)
t.start()
t.join()
