import sqlite3

#connect to database
conn = sqlite3.Connection('tickets.db')

#create cursor
c = conn.cursor()

#get the table name

c.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = c.fetchall()
print('Tables in Database tickets.db:', tables)

#get table info
c.execute("PRAGMA table_info('processed_tickets')")
table_information = c.fetchall()
print("Table Information:", table_information)


#fetch data from the table
table_name = 'processed_tickets'
c.execute("SELECT * FROM processed_tickets;")
rows = c.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("No data found in database. NULL")

conn.close()