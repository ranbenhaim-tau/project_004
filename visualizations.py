import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import mysql.connector
import os
import sys

# הגדרת עיצוב כללי לגרפים
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = [10, 6]

# הגדרות התחברות ל-DB
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'FLYTAU'
}

def get_db_connection():
    """מנסה להתחבר לדאטה-בייס. אם נכשל, מבקש סיסמה מהמשתמש."""
    try:
        # ניסיון ראשון עם ברירת המחדל (או משתנה סביבה)
        password = os.environ.get('DB_PASSWORD', DB_CONFIG['password'])
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=password,
            database=DB_CONFIG['database']
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Connection failed: {err}")
        # אם נכשל, נבקש סיסמה (רלוונטי להרצה ידנית בטרמינל)
        try:
            user_pass = input("Enter DB Password: ")
            conn = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=user_pass,
                database=DB_CONFIG['database']
            )
            return conn
        except Exception as e:
            print(f"Error connecting to DB: {e}")
            sys.exit(1)

# ==========================================
# דוח 1: הכנסות לפי מטוס ומחלקה
# ==========================================
def generate_revenue_summary(df):
    """מייצר תקציר מנהלים לדוח הכנסות."""
    top_revenue = df.loc[df['Total_Income'].idxmax()]
    total_revenue = df['Total_Income'].sum()
    
    # חישוב הכנסה לפי יצרן
    manufacturer_revenue = df.groupby('Manufacturer')['Total_Income'].sum().sort_values(ascending=False)
    top_manufacturer = manufacturer_revenue.index[0]
    
    summary = f"""
    --- תקציר מנהלים: דוח הכנסות ---
    1. סך ההכנסות הכולל: ${total_revenue:,.2f}
    2. הקטגוריה הרווחית ביותר: {top_revenue['Manufacturer']} {top_revenue['Size']} ({top_revenue['CLASS_Type']}) עם הכנסות של ${top_revenue['Total_Income']:,.2f}.
    3. היצרן המוביל בהכנסות: {top_manufacturer} (סך הכל: ${manufacturer_revenue.iloc[0]:,.2f}).
    4. המלצה: כדאי לשקול הגדלת היצע הטיסות במטוסים מסוג {top_revenue['Manufacturer']} {top_revenue['Size']}, שכן הם מציגים ביצועים עודפים משמעותית.
    ---------------------------------
    """
    print(summary)
    with open("revenue_executive_summary.txt", "w") as f:
        f.write(summary)


def plot_revenue_report(conn):
    # מעודכן לפי flytau_queries.sql (Query 2)
    query = """
    SELECT 
        a.Size, 
        a.Manufacturer, 
        t.CLASS_Type, 
        SUM(t.Price) AS Total_Income
    FROM
        TICKET_ORDER AS to1
    JOIN
        TICKET AS t
          ON t.Airplane_ID = to1.Airplane_ID
         AND t.Flight_ID = to1.Flight_ID
         AND t.SEAT_Row_num = to1.SEAT_Row_num
         AND t.SEAT_Column_number = to1.SEAT_Column_number
         AND t.CLASS_Type = to1.CLASS_Type
    JOIN
        AIRPLANE AS a ON t.Airplane_ID = a.ID
    JOIN
        `ORDER` AS o ON to1.Order_ID = o.ID
    WHERE o.Status IN ('Active','Completed')
    GROUP BY 
        a.Size, 
        a.Manufacturer, 
        t.CLASS_Type
    ORDER BY 
        a.Size, 
        a.Manufacturer, 
        t.CLASS_Type;
    """
    
    print("Fetching Revenue Data...")
    df = pd.read_sql(query, conn)
    
    if df.empty:
        print("No data found for Revenue Report.")
        return

    # הפקת תקציר מנהלים
    generate_revenue_summary(df)

    # יצירת עמודה משולבת לציר ה-X
    df['Plane_Type'] = df['Manufacturer'] + " (" + df['Size'] + ")"

    # ציור הגרף
    plt.figure(figsize=(12, 6))
    chart = sns.barplot(
        data=df, 
        x='Plane_Type', 
        y='Total_Income', 
        hue='CLASS_Type', 
        palette='viridis'
    )

    plt.title('Total Revenue by Aircraft Type and Class', fontsize=16, fontweight='bold')
    plt.xlabel('Aircraft (Manufacturer & Size)', fontsize=12)
    plt.ylabel('Total Income ($)', fontsize=12)
    plt.legend(title='Class Type')
    
    for container in chart.containers:
        chart.bar_label(container, fmt='%.0f', padding=3)

    plt.tight_layout()
    output_file = 'revenue_report_db.png'
    plt.savefig(output_file)
    print(f"Saved graph to {output_file}")
    plt.close()

# ==========================================
# דוח 2: מגמות ביטולים חודשיות
# ==========================================
def generate_cancellation_summary(df):
    """מייצר תקציר מנהלים לדוח ביטולים."""
    avg_cancellation = df['Cancellation_Rate'].mean()
    max_cancellation_row = df.loc[df['Cancellation_Rate'].idxmax()]
    
    # זיהוי חודשים בעייתיים (מעל 10% למשל)
    problematic_months = df[df['Cancellation_Rate'] > 10]
    
    summary = f"""
    --- תקציר מנהלים: מגמות ביטולים ---
    1. שיעור הביטול הממוצע: {avg_cancellation:.2f}%
    2. חודש השיא בביטולים: {max_cancellation_row['Month']} עם {max_cancellation_row['Cancellation_Rate']:.2f}%.
    3. חודשים חריגים (>10% ביטול): {', '.join(problematic_months['Month'].astype(str).tolist()) if not problematic_months.empty else "אין חריגות קיצוניות"}.
    4. מסקנה: {f"יש לבדוק את הסיבות לעלייה בביטולים בחודש {max_cancellation_row['Month']}." if max_cancellation_row['Cancellation_Rate'] > 10 else "שיעורי הביטול נראים סבירים ויציבים."}
    -----------------------------------
    """
    print(summary)
    with open("cancellation_executive_summary.txt", "w") as f:
        f.write(summary)


def plot_cancellation_report(conn):
    # מעודכן לפי flytau_queries.sql (Query 4) — ביטולי לקוח בלבד, לפי חודש רכישה
    query = """
    SELECT 
        DATE_FORMAT(Date_of_purchase, '%Y/%m') AS Month,
        ROUND(
            (SUM(CASE WHEN Status IN ('Customer Cancellation') THEN 1 ELSE 0 END) / COUNT(*)) * 100, 2
        ) AS Cancellation_Rate
    FROM 
        `ORDER`
    GROUP BY 
        DATE_FORMAT(Date_of_purchase, '%Y/%m')
    ORDER BY 
        Month;
    """

    print("Fetching Cancellation Data...")
    df = pd.read_sql(query, conn)

    if df.empty:
        print("No data found for Cancellation Report.")
        return

    # הפקת תקציר מנהלים
    generate_cancellation_summary(df)

    # ציור הגרף (Month הוא categorical, לכן נמנעים מ-fill_between שעלול להיכשל עם מחרוזות)
    plt.figure(figsize=(12, 6))
    sns.lineplot(
        data=df,
        x='Month',
        y='Cancellation_Rate',
        marker='o',
        linewidth=2.5
    )

    plt.axhline(y=10, color='gray', linestyle='--', label='Threshold (10%)')

    plt.title('Monthly Cancellation Rate Trends', fontsize=16, fontweight='bold')
    plt.xlabel('Month', fontsize=12)
    plt.ylabel('Cancellation Rate (%)', fontsize=12)
    plt.ylim(0, max(df['Cancellation_Rate'].max() + 5, 25))
    plt.legend()
    plt.xticks(rotation=45)

    for i, (x, y) in enumerate(zip(df['Month'], df['Cancellation_Rate'])):
        plt.text(i, y + 0.5, f'{y}%', ha='center', fontweight='bold')

    plt.tight_layout()
    output_file = 'cancellation_report_db.png'
    plt.savefig(output_file)
    print(f"Saved graph to {output_file}")
    plt.close()

# ==========================================
# Main
# ==========================================
if __name__ == "__main__":
    conn = get_db_connection()
    if conn and conn.is_connected():
        print("Connected to DB successfully.")
        plot_revenue_report(conn)
        plot_cancellation_report(conn)
        conn.close()
        print("Done.")
