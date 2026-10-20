import pandas as pd
import streamlit as st
from supabase import Client, create_client

st.set_page_config(page_title="Baby Matcher 👶", page_icon="👶", layout="centered")

# הגדרת חיבור ל-Supabase
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "1234")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("חסרים פרטי התחברות ל-Supabase. נא להגדיר ב-Secrets.")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# --- פונקציות מסד נתונים ---
def fetch_all_names():
    try:
        res = supabase.table("names").select("name, gender, category, meaning").execute()
        return res.data or []
    except Exception:
        return []

def insert_names_batch(records):
    try:
        supabase.table("names").upsert(records, on_conflict="name,category").execute()
        return True
    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {e}")
        return False

def save_swipe(room, user, baby_name, category):
    try:
        supabase.table("swipes").upsert({
            "room_code": room,
            "user_name": user,
            "baby_name": baby_name,
            "category": category
        }).execute()
    except Exception:
        pass

def get_matches(room):
    try:
        res = supabase.table("swipes").select("baby_name, user_name").eq("room_code", room).execute()
        data = res.data or []
        name_users = {}
        for row in data:
            name_users.setdefault(row["baby_name"], set()).add(row["user_name"])
        return [name for name, users in name_users.items() if len(users) >= 2]
    except Exception:
        return []

# --- אתחול משתני סשן ---
for key in ["room_code", "user_name", "selected_category", "current_index", "is_admin"]:
    if key not in st.session_state:
        st.session_state[key] = "" if key in ["room_code", "user_name"] else (False if key == "is_admin" else (0 if key == "current_index" else None))

# --- סרגל צדדי ופאנל מנהל ---
with st.sidebar.expander("🔐 פאנל מנהל (להוספת שמות)"):
    if not st.session_state.is_admin:
        pwd = st.text_input("סיסמה", type="password")
        if st.button("התחבר"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("סיסמה שגויה")
    else:
        st.success("מחובר כמנהל")
        if st.button("התנתק"):
            st.session_state.is_admin = False
            st.rerun()

if st.session_state.is_admin:
    st.title("🛠️ פאנל ניהול שמות")
    tab1, tab2, tab3 = st.tabs(["📤 העלאת קובץ", "➕ הוספה ידנית", "📋 מאגר קיים"])
    
    with tab1:
        st.write("העלה קובץ CSV עם העמודות: name, gender, category, meaning")
        uploaded_file = st.file_uploader("בחר קובץ CSV", type=["csv"])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df.head())
            if st.button("טען מסד נתונים לענן"):
                if {"name", "gender", "category"}.issubset(set(df.columns)):
                    if "meaning" not in df.columns:
                        df["meaning"] = ""
                    records = df[["name", "gender", "category", "meaning"]].to_dict(orient="records")
                    if insert_names_batch(records):
                        st.success(f"{len(records)} שמות נטענו בהצלחה!")
                else:
                    st.error("חסרות עמודות חובה בקובץ.")
    
    with tab2:
        with st.form("add_name"):
            n_name = st.text_input("שם")
            n_gen = st.selectbox("מין", ["זכר", "נקבה", "יוניסקס"])
            n_cat = st.text_input("קטגוריה")
            n_mean = st.text_area("משמעות")
            if st.form_submit_button("הוסף") and n_name and n_cat:
                if insert_names_batch([{"name": n_name, "gender": n_gen, "category": n_cat, "meaning": n_mean}]):
                    st.success("השם נוסף!")
    
    with tab3:
        all_names = fetch_all_names()
        st.write(f"סך הכל במאגר: {len(all_names)} שמות")
        if all_names:
            st.dataframe(pd.DataFrame(all_names))
    st.stop()

# --- מסך משתמש (התחברות לחדר) ---
if not st.session_state.room_code or not st.session_state.user_name:
    st.title("👶 בוחנים שמות יחד")
    with st.form("login_form"):
        room = st.text_input("קוד חדר משותף (למשל: harel2026)").strip().lower()
        user = st.text_input("השם שלך").strip()
        if st.form_submit_button("התחבר"):
            if room and user:
                st.session_state.room_code = room
                st.session_state.user_name = user
                st.rerun()
    st.stop()

# --- ממשק החלקה ---
st.sidebar.title(f"👤 {st.session_state.user_name}")
st.sidebar.caption(f"חדר: {st.session_state.room_code}")
if st.sidebar.button("🏠 חזרה לקטגוריות"):
    st.session_state.selected_category = None
    st.session_state.current_index = 0
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("💘 התאמות זוגיות (Matches)")
matches = get_matches(st.session_state.room_code)
if matches:
    for m in matches:
        st.sidebar.success(f"🎉 {m}")
else:
    st.sidebar.info("עוד אין התאמות")

NAMES_DB = fetch_all_names()

if not NAMES_DB:
    st.warning("המאגר ריק. היכנס לפאנל המנהל בסרגל הצד כדי להוסיף שמות.")
    st.stop()

if st.session_state.selected_category is None:
    st.title("בחר קטגוריה 📂")
    categories = sorted(list(set([item["category"] for item in NAMES_DB])))
    for cat in categories:
        count = sum(1 for item in NAMES_DB if item["category"] == cat)
        if st.button(f"{cat} ({count} שמות)", use_container_width=True):
            st.session_state.selected_category = cat
            st.session_state.current_index = 0
            st.rerun()
else:
    cat = st.session_state.selected_category
    names_in_cat = [item for item in NAMES_DB if item["category"] == cat]
    st.title(f"✨ {cat}")
    
    if st.session_state.current_index < len(names_in_cat):
        curr = names_in_cat[st.session_state.current_index]
        st.markdown(f"""
        <div style="padding: 30px; border-radius: 15px; border: 2px solid #ff4b4b; text-align: center; background-color: #fafafa; margin-bottom: 20px;">
            <h1 style="color: #ff4b4b; font-size: 48px;">{curr['name']}</h1>
            <p style="font-size: 18px; color: #555;"><b>משמעות:</b> {curr.get('meaning', '')}</p>
            <p style="font-size: 14px; color: #888;">מין: {curr['gender']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("❌ לא מתאים", use_container_width=True):
                st.session_state.current_index += 1
                st.rerun()
        with col2:
            if st.button("❤️ אהבתי", use_container_width=True):
                save_swipe(st.session_state.room_code, st.session_state.user_name, curr["name"], cat)
                st.session_state.current_index += 1
                st.rerun()
                
        st.progress((st.session_state.current_index + 1) / len(names_in_cat))
    else:
        st.success("סיימת את הקטגוריה הזו!")
        if st.button("בחר קטגוריה אחרת"):
            st.session_state.selected_category = None
            st.session_state.current_index = 0
            st.rerun()