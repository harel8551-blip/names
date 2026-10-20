import pandas as pd
import streamlit as st
from supabase import Client, create_client
import io

st.set_page_config(page_title="Baby Matcher 👶", page_icon="👶", layout="centered")

# --- הגדרות עיצוב לשפה העברית (RTL) ---
st.markdown(
    """
    <style>
    /* הפיכת כל האפליקציה לימין לשמאל */
    body, .stApp {
        direction: rtl;
    }
    
    /* יישור כל סוגי הטקסטים לימין */
    p, div, input, label, h1, h2, h3, h4, h5, h6, span, button, th, td {
        direction: rtl;
        text-align: right !important;
    }
    
    /* הזזת סרגל הצד (Sidebar) לצד ימין */
    [data-testid="stSidebar"] {
        right: 0 !important;
        left: auto !important;
    }
    
    /* הזזת כפתור הפתיחה/סגירה של סרגל הצד שמאלה כדי שלא יוסתר */
    [data-testid="collapsedControl"] {
        right: auto !important;
        left: 1rem !important;
    }
    
    /* יישור התראות (Success/Error) לימין */
    [data-testid="stAlert"] {
        direction: rtl;
        text-align: right;
    }
    
    /* יישור רשימות נפתחות (Selectbox) לימין */
    .stSelectbox div[data-baseweb="select"] {
        text-align: right;
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

# משיכת כל השמות (עוקף את מגבלת ה-1000 של Supabase)
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
        if role in ["אבא", "אמא"]:
            for u in users_in_room:
                if u["role"] == role and u["user_name"] != user:
                    return False, f"התפקיד '{role}' כבר תפוס על ידי '{u['user_name']}' בחדר הזה."
        supabase.table("room_users").upsert({"room_code": room, "user_name": user, "role": role}).execute()
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
            "מין": info.get("gender", ""),
            "קטגוריה": info.get("category", "לא צוין"),
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
for key in ["room_code", "user_name", "user_role", "selected_gender", "selected_category", "is_admin", "view_mode"]:
    if key not in st.session_state:
        if key in ["room_code", "user_name", "user_role"]:
            st.session_state[key] = ""
        elif key == "is_admin":
            st.session_state[key] = False
        elif key == "view_mode":
            st.session_state[key] = "swipe"
        else:
            st.session_state[key] = None

# פאנל מנהל
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
    tab1, tab2, tab3 = st.tabs(["📤 טעינת רשימת טקסט", "➕ הוספה ידנית", "📋 מאגר קיים ואיפוס"])
    
    with tab1:
        st.write("הדבק כאן ישירות את תוכן ה-CSV (כולל שורת הכותרת `name,gender,category,meaning`):")
        pasted_text = st.text_area("טקסט ה-CSV", height=250)
        if st.button("טען את הרשימה לענן", type="primary"):
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
                        st.error("חסרות עמודות חובה (name, gender, category). ודא שהשורה הראשונה היא: name,gender,category,meaning")
                except Exception as e:
                    st.error(f"שגיאה בעיבוד הטקסט: {e}")
            else:
                st.warning("נא להדביק טקסט.")
    
    with tab2:
        with st.form("add_name"):
            n_name = st.text_input("שם")
            n_gen = st.selectbox("מין", ["זכר", "נקבה", "יוניסקס"])
            n_cat = st.text_input("קטגוריה (למשל: טבע ונוף - מים)")
            n_mean = st.text_area("משמעות")
            if st.form_submit_button("הוסף") and n_name and n_cat:
                if insert_names_batch([{"name": n_name, "gender": n_gen, "category": n_cat, "meaning": n_mean}]):
                    st.success("השם נוסף!")
    
    with tab3:
        all_names = fetch_all_names()
        st.write(f"סך הכל במאגר כרגע: **{len(all_names)}** שמות")
        if st.button("🗑️ מחק את כל השמות במאגר (איפוס מלא)", type="secondary"):
            if delete_all_names():
                st.success("כל השמות נמחקו בהצלחה! כעת ניתן לטעון רשימה חדשה.")
                st.rerun()
        if all_names:
            st.dataframe(pd.DataFrame(all_names), use_container_width=True)
    st.stop()

# מסך התחברות לחדר
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
    st.stop()

# סרגל צד - ניווט
st.sidebar.title(f"👤 {st.session_state.user_name} ({st.session_state.user_role})")
st.sidebar.caption(f"חדר משפחתי: {st.session_state.room_code}")

if st.session_state.selected_gender:
    st.sidebar.info(f"מחפשים שם ל: **{st.session_state.selected_gender}**")
    if st.sidebar.button("🔄 החלף מין (בן/בת)", use_container_width=True):
        st.session_state.selected_gender = None
        st.session_state.selected_category = None
        st.session_state.view_mode = "swipe"
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 התאמות")

if st.sidebar.button("💘 התאמה זוגית מושלמת", use_container_width=True):
    st.session_state.view_mode = "parent_matches"
    st.rerun()

if st.sidebar.button("👨‍👩‍👧‍👦 אהוב על המשפחה", use_container_width=True):
    st.session_state.view_mode = "family_matches"
    st.rerun()

st.sidebar.markdown("---")

if st.sidebar.button("📂 חזרה לבחירת קטגוריה", use_container_width=True):
    st.session_state.view_mode = "swipe"
    st.session_state.selected_category = None
    st.rerun()

NAMES_DB = fetch_all_names()
if not NAMES_DB:
    st.warning("המאגר ריק. היכנס לפאנל המנהל בסרגל הצד כדי להוסיף שמות.")
    st.stop()

# ניתוב מסכים
if st.session_state.view_mode == "parent_matches":
    st.title("💘 התאמה זוגית מושלמת")
    st.write("כל השמות שגם אבא וגם אמא הסכימו עליהם:")
    p_matches, _ = get_matches(st.session_state.room_code)
    if p_matches:
        df = build_matches_df(p_matches, NAMES_DB)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("עדיין אין הסכמה זוגית על אף שם.")

elif st.session_state.view_mode == "family_matches":
    st.title("👨‍👩‍👧‍👦 אהוב על המשפחה")
    st.write("שמות שלפחות אחד מההורים אהב, ועוד מישהו מהמשפחה תמך בהם:")
    _, f_matches = get_matches(st.session_state.room_code)
    if f_matches:
        df = build_matches_df(f_matches, NAMES_DB)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("עדיין אין שמות עם תמיכה משפחתית משולבת.")

elif st.session_state.view_mode == "swipe":
    # שלב 1: בחירת בן / בת לפני הכל!
    if st.session_state.selected_gender is None:
        st.title("למי מחפשים שם? 👶")
        st.write("בחר כדי שנסנן עבורך את השמות והקטגוריות הרלוונטיים:")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("👦 בן\n\n(כולל יוניסקס)", use_container_width=True):
                st.session_state.selected_gender = "בן"
                st.rerun()
        with col2:
            if st.button("👧 בת\n\n(כולל יוניסקס)", use_container_width=True):
                st.session_state.selected_gender = "בת"
                st.rerun()
        with col3:
            if st.button("✨ יוניסקס בלבד", use_container_width=True):
                st.session_state.selected_gender = "יוניסקס"
                st.rerun()
        st.stop()

    user_swiped_names = get_user_swiped_names(st.session_state.room_code, st.session_state.user_name)
    gender_filtered_db = [
        item for item in NAMES_DB 
        if matches_gender_filter(item.get("gender", ""), st.session_state.selected_gender)
    ]

    # שלב 2: בחירת קטגוריה ותת-קטגוריה
    if st.session_state.selected_category is None:
        st.title(f"בחר קטגוריה ({st.session_state.selected_gender}) 📂")
        
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

    # שלב 3: מסך ההחלקה
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
        
        if len(unswiped_names_in_cat) > 0:
            curr = unswiped_names_in_cat[0]
            st.markdown(f"""
            <div style="padding: 30px; border-radius: 15px; border: 2px solid #ff4b4b; text-align: center; background-color: #fafafa; margin-bottom: 20px;">
                <h1 style="color: #ff4b4b; font-size: 48px; margin-bottom: 10px;">{curr['name']}</h1>
                <p style="font-size: 18px; color: #444;"><b>משמעות:</b> {curr.get('meaning', 'אין פירוש')}</p>
                <p style="font-size: 14px; color: #888;">מין: {curr['gender']} | קטגוריות: {curr['category']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ לא מתאים", use_container_width=True):
                    save_swipe(st.session_state.room_code, st.session_state.user_name, st.session_state.user_role, curr["name"], display_title, "reject")
                    st.rerun()
            with col2:
                if st.button("❤️ אהבתי", use_container_width=True):
                    save_swipe(st.session_state.room_code, st.session_state.user_name, st.session_state.user_role, curr["name"], display_title, "like")
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
