import pandas as pd
import streamlit as st
from supabase import Client, create_client
import io

st.set_page_config(page_title="Baby Matcher 👶", page_icon="👶", layout="centered")

# --- הגדרות עיצוב לשפה העברית (RTL) ותפריט עליון ---
st.markdown(
    """
    <style>
    /* הפיכת כל האפליקציה לימין לשמאל */
    body, .stApp {
        direction: rtl;
    }
    
    /* יישור טקסטים לימין */
    p, div, input, label, h1, h2, h3, h4, h5, h6, span, button, th, td {
        direction: rtl;
        text-align: right !important;
    }
    
    /* הסתרת סרגל הצד המקורי לחלוטין */
    [data-testid="collapsedControl"], [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* יישור התראות לימין */
    [data-testid="stAlert"] {
        direction: rtl;
        text-align: right;
    }
    
    /* עיצוב רשימות נפתחות */
    .stSelectbox div[data-baseweb="select"] {
        text-align: right;
    }
    
    /* --- עיצוב מושלם לטבלאות --- */
    .rtl-table {
        width: 100%;
        direction: rtl;
        text-align: right;
        border-collapse: collapse;
        font-family: sans-serif;
        margin-top: 10px;
        margin-bottom: 20px;
        background-color: white;
    }
    .rtl-table th, .rtl-table td {
        border: 1px solid #e0e0e0;
        padding: 12px;
        text-align: right !important;
    }
    .rtl-table th {
        background-color: #f8f9fa;
        font-weight: bold;
        color: #333;
    }
    .rtl-table tr:nth-child(even) {
        background-color: #fafafa;
    }
    .rtl-table tr:hover {
        background-color: #f1f1f1;
    }
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
        return True
    except Exception as e:
        st.error(f"שגיאה במחיקה: {e}")
        return False

def insert_names_batch(records):
    try:
        supabase.table("names").upsert(records, on_conflict="name,category").execute()
        return True
    except Exception as e:
        st.error(f"שגיאה בטעינת הנתונים: {e}")
        return False

def check_and_register_user(room, user, role):
    try:
        res = supabase.table("room_users").select("user_name, role").eq("room_code", room).execute()
        users_in_room = res.data or []
        
        # 1. קודם כל נוודא שהתפקיד לא תפוס על ידי משתמש *אחר* בחדר
        if role in ["אבא", "אמא"]:
            for u in users_in_room:
                if u["role"] == role and u["user_name"] != user:
                    return False, f"התפקיד '{role}' כבר תפוס על ידי '{u['user_name']}' בחדר הזה."
        
        # 2. נבדק אם המשתמש כבר קיים בחדר
        for u in users_in_room:
            if u["user_name"] == user:
                # אם הוא קיים אבל שינה תפקיד, נעדכן את מסד הנתונים
                if u["role"] != role:
                    supabase.table("room_users").update({"role": role}).eq("room_code", room).eq("user_name", user).execute()
                return True, ""
                
        # 3. אם זה משתמש חדש לגמרי
        supabase.table("room_users").insert({"room_code": room, "user_name": user, "role": role}).execute()
        return True, ""
    except Exception as e:
        return False, f"שגיאת מסד נתונים: {e}"

def save_swipe(room, user, role, baby_name, category, status):
    try:
        supabase.table("swipes").upsert({
            "room_code": room,
            "user_name": user,
            "role": role,
            "baby_name": baby_name,
            "category": category,
            "status": status
        }).execute()
    except Exception:
        pass

def get_user_swiped_names(room, user):
    all_data = []
    batch_size = 1000
    start = 0
    try:
        while True:
            res = supabase.table("swipes").select("baby_name").eq("room_code", room).eq("user_name", user).range(start, start + batch_size - 1).execute()
            data = res.data or []
            all_data.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        return set([row["baby_name"] for row in all_data])
    except Exception:
        return set()

def get_who_liked_data(room, baby_name, current_user):
    try:
        res = supabase.table("swipes").select("user_name, role").eq("room_code", room).eq("baby_name", baby_name).eq("status", "like").neq("user_name", current_user).execute()
        return res.data or []
    except Exception:
        return []

def get_my_likes(room, user):
    all_data = []
    batch_size = 1000
    start = 0
    try:
        while True:
            res = supabase.table("swipes").select("baby_name").eq("room_code", room).eq("user_name", user).eq("status", "like").range(start, start + batch_size - 1).execute()
            data = res.data or []
            all_data.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        return [row["baby_name"] for row in all_data]
    except Exception:
        return []

def remove_like(room, user, baby_name):
    try:
        supabase.table("swipes").update({"status": "reject"}).eq("room_code", room).eq("user_name", user).eq("baby_name", baby_name).execute()
    except Exception:
        pass

def get_matches(room):
    all_data = []
    batch_size = 1000
    start = 0
    try:
        while True:
            res = supabase.table("swipes").select("baby_name, user_name, role").eq("room_code", room).eq("status", "like").range(start, start + batch_size - 1).execute()
            data = res.data or []
            all_data.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        
        name_likes = {}
        for row in all_data:
            b_name = row["baby_name"]
            if b_name not in name_likes:
                name_likes[b_name] = {"users": [], "roles": []}
            if row["user_name"] not in name_likes[b_name]["users"]:
                name_likes[b_name]["users"].append(row["user_name"])
                name_likes[b_name]["roles"].append(row.get("role") or "אחר")
            
        parent_matches = []
        family_matches = []
        for b_name, info in name_likes.items():
            users = info["users"]
            roles = info["roles"]
            has_aba = "אבא" in roles
            has_ima = "אמא" in roles
            has_family = any(r not in ["אבא", "אמא"] for r in roles)
            users_str = ", ".join(users)
            
            if has_aba and has_ima:
                parent_matches.append({"name": b_name, "users": users_str})
            elif (has_aba or has_ima) and has_family:
                family_matches.append({"name": b_name, "users": users_str})
                
        return parent_matches, family_matches
    except Exception:
        return [], []

def build_matches_df(matches_list, names_db):
    db_dict = {item["name"]: item for item in names_db}
    rows = []
    for m in matches_list:
        b_name = m["name"]
        info = db_dict.get(b_name, {})
        rows.append({
            "שם": b_name,
            "משמעות": info.get("meaning", "אין פירוש"),
            "מי הסכים": m["users"]
        })
    return pd.DataFrame(rows)

def get_item_categories(item):
    c_str = str(item.get("category", ""))
    return [c.strip() for c in c_str.split(",") if c.strip()]

def matches_gender_filter(item_gender, selected_filter):
    if selected_filter == "בן":
        return item_gender in ["זכר", "יוניסקס"]
    elif selected_filter == "בת":
        return item_gender in ["נקבה", "יוניסקס"]
    elif selected_filter == "יוניסקס":
        return item_gender == "יוניסקס"
    return True

# אתחול משתני סשן
for key in ["room_code", "user_name", "user_role", "selected_gender", "selected_category", "is_admin", "view_mode", "match_alert", "perfect_match_alert"]:
    if key not in st.session_state:
        if key in ["room_code", "user_name", "user_role"]:
            st.session_state[key] = ""
        elif key == "is_admin":
            st.session_state[key] = False
        elif key == "view_mode":
            st.session_state[key] = "swipe"
        else:
            st.session_state[key] = None

# --- מצב מנהל ---
if st.session_state.is_admin:
    st.title("🛠️ פאנל ניהול שמות")
    if st.button("⬅️ יציאה מניהול וחזרה", type="primary"):
        st.session_state.is_admin = False
        st.rerun()
        
    tab1, tab2, tab3 = st.tabs(["📤 טעינת רשימת טקסט", "➕ הוספה ידנית", "📋 מאגר קיים ואיפוס"])
    with tab1:
        st.write("הדבק כאן ישירות את תוכן ה-CSV (כולל שורת הכותרת `name,gender,category,meaning`):")
        pasted_text = st.text_area("טקסט ה-CSV", height=250)
        if st.button("טען את הרשימה לענן"):
            if pasted_text.strip():
                try:
                    df = pd.read_csv(io.StringIO(pasted_text), on_bad_lines='skip')
                    if {"name", "gender", "category"}.issubset(set(df.columns)):
                        if "meaning" not in df.columns:
                            df["meaning"] = ""
                        df["meaning"] = df["meaning"].fillna("")
                        df = df.drop_duplicates(subset=["name"])
                        records = df[["name", "gender", "category", "meaning"]].to_dict(orient="records")
                        if insert_names_batch(records):
                            st.success(f"🎉 {len(records)} שמות נטענו בהצלחה לענן!")
                    else:
                        st.error("חסרות עמודות חובה.")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
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
        st.write(f"סך הכל במאגר כרגע: **{len(all_names)}** שמות")
        if st.button("🗑️ מחק את כל השמות במאגר (איפוס מלא)", type="secondary"):
            if delete_all_names():
                st.success("כל השמות נמחקו בהצלחה!")
                st.rerun()
        if all_names:
            df_all = pd.DataFrame(all_names)
            st.markdown(df_all.to_html(index=False, classes="rtl-table"), unsafe_allow_html=True)
    st.stop()

# --- מסך התחברות רגיל ---
if not st.session_state.room_code or not st.session_state.user_name:
    st.title("👶 בוחנים שמות יחד")
    with st.form("login_form"):
        room = st.text_input("קוד חדר משותף (אותו קוד לכל המשפחה)").strip().lower()
        user = st.text_input("השם שלך (למשל: הראל, טליה)").strip()
        role = st.selectbox("התפקיד שלך במשפחה", ["אבא", "אמא", "סבא", "סבתא", "דוד", "דודה", "אח/ות", "אחר"])
        if st.form_submit_button("היכנס לחדר"):
            if room and user:
                success, msg = check_and_register_user(room, user, role)
                if success:
                    st.session_state.room_code = room
                    st.session_state.user_name = user
                    st.session_state.user_role = role
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("נא למלא חדר ושם.")
                
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.expander("🔐 פאנל מנהל (להוספת שמות למאגר)"):
        pwd = st.text_input("סיסמה", type="password")
        if st.button("התחבר"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("סיסמה שגויה")
    st.stop()

# ==========================================
# --- תפריט הניווט העליון (למשתמשים מחוברים) ---
# ==========================================
st.markdown(f"<div style='text-align:center; color:#888; margin-bottom: 10px;'>👤 <b>{st.session_state.user_name}</b> ({st.session_state.user_role}) | חדר: <b>{st.session_state.room_code}</b></div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔍 חיפוש", use_container_width=True):
        st.session_state.view_mode = "swipe"
        st.session_state.selected_category = None
        st.rerun()
with col2:
    if st.button("👑 התאמות", use_container_width=True):
        st.session_state.view_mode = "matches"
        st.rerun()
with col3:
    if st.button("💖 אהבתי", use_container_width=True):
        st.session_state.view_mode = "my_likes"
        st.rerun()
st.markdown("---")

NAMES_DB = fetch_all_names()
if not NAMES_DB:
    st.warning("המאגר ריק. התנתק והיכנס לפאנל המנהל כדי להוסיף שמות.")
    st.stop()

# --- ניתוב למסכים ---

if st.session_state.view_mode == "matches":
    st.title("ההתאמות בחדר 👑")
    p_matches, f_matches = get_matches(st.session_state.room_code)
    
    t1, t2 = st.tabs(["💘 התאמה זוגית מושלמת", "👨‍👩‍👧‍👦 אהוב על המשפחה"])
    with t1:
        st.write("כל השמות שגם אבא וגם אמא הסכימו עליהם:")
        if p_matches:
            st.markdown(build_matches_df(p_matches, NAMES_DB).to_html(index=False, classes="rtl-table"), unsafe_allow_html=True)
        else:
            st.info("עדיין אין הסכמה זוגית על אף שם.")
    with t2:
        st.write("שמות שלפחות אחד מההורים אהב, ועוד מישהו מהמשפחה תמך בהם:")
        if f_matches:
            st.markdown(build_matches_df(f_matches, NAMES_DB).to_html(index=False, classes="rtl-table"), unsafe_allow_html=True)
        else:
            st.info("עדיין אין שמות עם תמיכה משפחתית משולבת.")

elif st.session_state.view_mode == "my_likes":
    st.title("💖 השמות שאהבתי")
    st.write("עברת על השמות והתחרטת? אפשר להסיר אותם כדי שלא יופיעו בהתאמות.")
    
    my_liked_names = get_my_likes(st.session_state.room_code, st.session_state.user_name)
    if not my_liked_names:
        st.info("עדיין לא אהבת אף שם. יאללה, חזור לחיפוש! 😎")
    else:
        db_dict = {item["name"]: item for item in NAMES_DB}
        for name in my_liked_names:
            info = db_dict.get(name, {})
            meaning = info.get("meaning", "אין פירוש")
            col_txt, col_btn = st.columns([4, 1])
            with col_txt:
                st.markdown(f"<div style='padding-top: 5px; font-size: 18px;'><b>{name}</b> - <span style='color: #666; font-size: 15px;'>{meaning}</span></div>", unsafe_allow_html=True)
            with col_btn:
                if st.button("🗑️ הסר", key=f"remove_{name}", use_container_width=True):
                    remove_like(st.session_state.room_code, st.session_state.user_name, name)
                    st.rerun()
            st.markdown("<hr style='margin: 5px 0; border: none; border-bottom: 1px solid #eee;'>", unsafe_allow_html=True)

elif st.session_state.view_mode == "swipe":
    # 1. בחירת מין
    if st.session_state.selected_gender is None:
        st.title("למי מחפשים שם? 👶")
        st.write("בחר כדי שנסנן עבורך את השמות והקטגוריות הרלוונטיים:")
        col_m, col_f, col_u = st.columns(3)
        with col_m:
            if st.button("👦 בן\n\n(כולל יוניסקס)", use_container_width=True):
                st.session_state.selected_gender = "בן"
                st.rerun()
        with col_f:
            if st.button("👧 בת\n\n(כולל יוניסקס)", use_container_width=True):
                st.session_state.selected_gender = "בת"
                st.rerun()
        with col_u:
            if st.button("✨ יוניסקס", use_container_width=True):
                st.session_state.selected_gender = "יוניסקס"
                st.rerun()
        st.stop()

    user_swiped_names = get_user_swiped_names(st.session_state.room_code, st.session_state.user_name)
    gender_filtered_db = [
        item for item in NAMES_DB 
        if matches_gender_filter(item.get("gender", ""), st.session_state.selected_gender)
    ]

    # 2. בחירת קטגוריה
    if st.session_state.selected_category is None:
        st.title(f"בחר קטגוריה ({st.session_state.selected_gender}) 📂")
        if st.button("🔄 חזור ובחר מין אחר", use_container_width=True):
            st.session_state.selected_gender = None
            st.rerun()
            
        cat_tree = {}
        for item in gender_filtered_db:
            if item["name"] in user_swiped_names:
                continue
            for full_cat in get_item_categories(item):
                if " - " in full_cat:
                    main_c, sub_c = [x.strip() for x in full_cat.split(" - ", 1)]
                else:
                    main_c, sub_c = full_cat.strip(), "כללי"
                
                if main_c not in cat_tree:
                    cat_tree[main_c] = {}
                cat_tree[main_c][ full_cat ] = cat_tree[main_c].get(full_cat, 0) + 1

        if not cat_tree:
            st.success("🎉 עברת על כל השמות במאגר עבור הבחירה הזו!")
        else:
            for main_c in sorted(cat_tree.keys()):
                sub_dict = cat_tree[main_c]
                unique_in_main = len(set(
                    item["name"] for item in gender_filtered_db
                    if item["name"] not in user_swiped_names and any(
                        c == main_c or c.startswith(main_c + " - ") for c in get_item_categories(item)
                    )
                ))
                
                with st.expander(f"📁 **{main_c}** ({unique_in_main} שמות נותרו)"):
                    if len(sub_dict) > 1:
                        if st.button(f"🌟 כל השמות ב-{main_c} ({unique_in_main})", key=f"ALL_{main_c}", use_container_width=True):
                            st.session_state.selected_category = f"MAIN:{main_c}"
                            st.rerun()
                        st.markdown("---")
                    
                    for full_cat, cnt in sorted(sub_dict.items()):
                        display_sub = full_cat.split(" - ", 1)[1] if " - " in full_cat else full_cat
                        if st.button(f"🔹 {display_sub} ({cnt} שמות)", key=f"SUB_{full_cat}", use_container_width=True):
                            st.session_state.selected_category = full_cat
                            st.rerun()

    # 3. מסך החלקה
    else:
        sel_cat = st.session_state.selected_category
        if sel_cat.startswith("MAIN:"):
            main_name = sel_cat.replace("MAIN:", "")
            display_title = f"{main_name} (כל השמות)"
            matching_items = [
                item for item in gender_filtered_db
                if any(c == main_name or c.startswith(main_name + " - ") for c in get_item_categories(item))
            ]
        else:
            display_title = sel_cat
            matching_items = [
                item for item in gender_filtered_db
                if sel_cat in get_item_categories(item)
            ]

        unswiped_names_in_cat = [item for item in matching_items if item["name"] not in user_swiped_names]
        
        st.subheader(f"✨ {display_title} ({st.session_state.selected_gender})")
        if st.button("📂 חזור לבחירת קטגוריות", use_container_width=True):
            st.session_state.selected_category = None
            st.rerun()

        # תצוגת פופ-אפ התאמה מושלמת
        if st.session_state.perfect_match_alert:
            pm = st.session_state.perfect_match_alert
            baby_emoji = "👦" if pm["gender"] == "זכר" else "👧" if pm["gender"] == "נקבה" else "👶"
            
            st.balloons()
            st.markdown(f"""
            <div style="text-align: center; padding: 50px 20px; background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); border-radius: 20px; border: 3px solid #ff4b4b; box-shadow: 0 10px 20px rgba(0,0,0,0.1); margin-bottom: 30px; margin-top: 20px;">
                <h1 style="font-size: 38px; color: #ff4b4b; margin-bottom: 10px;">🎉 התאמה זוגית מושלמת! 🎉</h1>
                <h2 style="font-size: 26px; color: #333;">אבא ואמא הסכימו על השם: <br><br><b style="font-size: 40px; color: #ff4b4b;">{pm['name']}</b></h2>
                <div style="font-size: 110px; animation: bounce 1s infinite; margin: 30px 0;">{baby_emoji}</div>
                <style>
                    @keyframes bounce {{
                        0%, 100% {{ transform: translateY(0); }}
                        50% {{ transform: translateY(-30px); }}
                    }}
                </style>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 איזה יופי! המשך לשם הבא", use_container_width=True, type="primary"):
                st.session_state.perfect_match_alert = None
                st.rerun()
            st.stop()
            
        # תצוגת התאמה רגילה
        elif st.session_state.match_alert:
            st.toast(st.session_state.match_alert, icon="💘")
            st.success(st.session_state.match_alert)
            st.session_state.match_alert = None
        
        # כרטיס החלקה
        if len(unswiped_names_in_cat) > 0:
            curr = unswiped_names_in_cat[0]
            st.markdown(f"""
            <div style="padding: 30px; border-radius: 15px; border: 2px solid #ff4b4b; text-align: center; background-color: #fafafa; margin-bottom: 20px; margin-top: 20px;">
                <h1 style="color: #ff4b4b; font-size: 48px; margin-bottom: 10px;">{curr['name']}</h1>
                <p style="font-size: 18px; color: #444;"><b>משמעות:</b> {curr.get('meaning', 'אין פירוש')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ לא מתאים", use_container_width=True):
                    save_swipe(st.session_state.room_code, st.session_state.user_name, st.session_state.user_role, curr["name"], display_title, "reject")
                    st.rerun()
            with col2:
                if st.button("❤️ אהבתי", use_container_width=True):
                    other_likes_data = get_who_liked_data(st.session_state.room_code, curr["name"], st.session_state.user_name)
                    save_swipe(st.session_state.room_code, st.session_state.user_name, st.session_state.user_role, curr["name"], display_title, "like")
                    
                    other_roles = [x["role"] for x in other_likes_data]
                    other_names = [x["user_name"] for x in other_likes_data]
                    current_role = st.session_state.user_role
                    
                    is_perfect_match = False
                    if current_role == "אבא" and "אמא" in other_roles:
                        is_perfect_match = True
                    elif current_role == "אמא" and "אבא" in other_roles:
                        is_perfect_match = True
                        
                    if is_perfect_match:
                        st.session_state.perfect_match_alert = {"name": curr["name"], "gender": curr["gender"]}
                    elif other_names:
                        st.session_state.match_alert = f"🎉 התאמה על השם '{curr['name']}' עם: {', '.join(set(other_names))}!"
                        
                    st.rerun()
                    
            total_in_cat = len(matching_items)
            progress = (total_in_cat - len(unswiped_names_in_cat)) / total_in_cat if total_in_cat > 0 else 1.0
            st.progress(progress)
            st.caption(f"נותרו עוד {len(unswiped_names_in_cat)} שמות בקטגוריה זו")
        else:
            st.success("סיימת את כל השמות בקטגוריה הזו!")
            if st.button("חזרה לבחירת קטגוריות", type="primary"):
                st.session_state.selected_category = None
                st.rerun()
