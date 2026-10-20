import pandas as pd
import streamlit as st
from supabase import Client, create_client
import io
import random

st.set_page_config(page_title="Baby Matcher 👶", page_icon="👶", layout="centered")

# --- הגדרות עיצוב לשפה העברית (RTL), תפריט עליון וכפתורים מוגדלים למובייל ---
st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; }
    p, div, input, label, h1, h2, h3, h4, h5, h6, span, button, th, td { direction: rtl; text-align: right !important; }
    [data-testid="collapsedControl"], [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stAlert"] { direction: rtl; text-align: right; }
    .stSelectbox div[data-baseweb="select"] { text-align: right; }
    
    /* הגדלת כל הכפתורים באפליקציה שיהיו נוחים ללחיצה בטלפון */
    div.stButton > button {
        border-radius: 15px !important;
        min-height: 55px;
        font-size: 18px !important;
        font-weight: bold !important;
    }
    
    /* --- עיצוב מושלם לטבלאות --- */
    .rtl-table {
        width: 100%; direction: rtl; text-align: right; border-collapse: collapse;
        font-family: sans-serif; margin-top: 10px; margin-bottom: 20px; background-color: white;
    }
    .rtl-table th, .rtl-table td { border: 1px solid #e0e0e0; padding: 12px; text-align: right !important; }
    .rtl-table th { background-color: #f8f9fa; font-weight: bold; color: #333; }
    .rtl-table tr:nth-child(even) { background-color: #fafafa; }
    .rtl-table tr:hover { background-color: #f1f1f1; }
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- אופטימיזציה: משיכת שמות במטמון מהיר ---
@st.cache_data(ttl=3600)
def fetch_all_names():
    all_data = []
    batch_size = 1000
    start = 0
    try:
        while True:
            res = supabase.table("names").select("name, gender, category, meaning").range(start, start + batch_size - 1).execute()
            data = res.data or []
            all_data.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        return all_data
    except Exception:
        return []

def delete_all_names():
    try:
        supabase.table("names").delete().neq("name", "___non_existent___").execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        return False

def insert_names_batch(records):
    try:
        supabase.table("names").upsert(records, on_conflict="name,category").execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {e}")
        return False

# --- משיכת מידע מרוכזת ---
def fetch_room_swipes(room):
    all_data = []
    batch_size = 1000
    start = 0
    try:
        while True:
            res = supabase.table("swipes").select("baby_name, user_name, role, status").eq("room_code", room).range(start, start + batch_size - 1).execute()
            data = res.data or []
            all_data.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        return all_data
    except Exception:
        return []

def get_room_users(room):
    try:
        res = supabase.table("room_users").select("user_name, role").eq("room_code", room).execute()
        return res.data or []
    except Exception:
        return []

def check_and_register_user(room, user, role):
    try:
        users_in_room = get_room_users(room)
        if role in ["אבא", "אמא"]:
            for u in users_in_room:
                if u["role"] == role and u["user_name"] != user:
                    return False, f"התפקיד '{role}' כבר תפוס על ידי '{u['user_name']}' בחדר הזה."
        for u in users_in_room:
            if u["user_name"] == user:
                if u["role"] != role:
                    supabase.table("room_users").update({"role": role}).eq("room_code", room).eq("user_name", user).execute()
                return True, ""
        supabase.table("room_users").insert({"room_code": room, "user_name": user, "role": role}).execute()
        return True, ""
    except Exception as e:
        return False, f"שגיאת מסד נתונים: {e}"

def save_swipe(room, user, role, baby_name, category, status):
    try:
        supabase.table("swipes").upsert({
            "room_code": room, "user_name": user, "role": role, "baby_name": baby_name, "category": category, "status": status
        }).execute()
    except Exception:
        pass

def remove_like(room, user, baby_name):
    try:
        supabase.table("swipes").update({"status": "reject"}).eq("room_code", room).eq("user_name", user).eq("baby_name", baby_name).execute()
    except Exception:
        pass

def get_user_swiped_names_local(room_swipes, user):
    return set([row["baby_name"] for row in room_swipes if row["user_name"] == user])

def get_matches_local(room_swipes):
    name_likes = {}
    for row in room_swipes:
        if row["status"] == "like":
            b_name = row["baby_name"]
            if b_name not in name_likes:
                name_likes[b_name] = {"users": [], "roles": []}
            if row["user_name"] not in name_likes[b_name]["users"]:
                name_likes[b_name]["users"].append(row["user_name"])
                name_likes[b_name]["roles"].append(row.get("role") or "אחר")
    
    parent_matches, family_matches = [], []
    for b_name, info in name_likes.items():
        users, roles = info["users"], info["roles"]
        has_aba, has_ima = "אבא" in roles, "אמא" in roles
        has_family = any(r not in ["אבא", "אמא"] for r in roles)
        users_str = ", ".join(users)
        
        if has_aba and has_ima:
            parent_matches.append({"name": b_name, "users": users_str})
        elif (has_aba or has_ima) and has_family:
            family_matches.append({"name": b_name, "users": users_str})
            
    return parent_matches, family_matches

def get_my_likes_local(room_swipes, user):
    return [row["baby_name"] for row in room_swipes if row["user_name"] == user and row["status"] == "like"]

def build_matches_df(matches_list, names_db):
    db_dict = {item["name"]: item for item in names_db}
    rows = []
    for m in matches_list:
        b_name = m["name"]
        info = db_dict.get(b_name, {})
        rows.append({"שם": b_name, "משמעות": info.get("meaning", "אין פירוש"), "מי הסכים": m["users"]})
    return pd.DataFrame(rows)

def get_item_categories(item):
    return [c.strip() for c in str(item.get("category", "")).split(",") if c.strip()]

def matches_gender_filter(item_gender, selected_filter):
    if selected_filter == "בן": return item_gender in ["זכר", "יוניסקס"]
    elif selected_filter == "בת": return item_gender in ["נקבה", "יוניסקס"]
    elif selected_filter == "יוניסקס": return item_gender == "יוניסקס"
    return True

# --- אתחול משתני סשן ---
for key in ["room_code", "user_name", "user_role", "selected_gender", "selected_category", "is_admin", "view_mode", "match_alert", "perfect_match_alert", "sort_order", "random_seed", "search_query"]:
    if key not in st.session
