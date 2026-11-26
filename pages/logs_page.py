"""System activity history page."""
import pandas as pd
import streamlit as st


ACTION_AR = {
    "CREATE_TASK": "إنشاء مهمة",
    "UPDATE_TASK": "تعديل مهمة",
    "DELETE_TASK": "حذف مهمة",
}


def show_logs_page(company) -> None:
    st.header("📜 سجل الأنشطة")
    logs = company.db.list_system_logs()
    if not logs:
        st.info("لا توجد أنشطة مسجلة بعد.")
        return
    frame = pd.DataFrame(logs)
    frame["action"] = frame["action"].map(lambda value: ACTION_AR.get(value, value))
    frame = frame.rename(columns={
        "id": "الرقم", "action": "العملية",
        "entity_type": "نوع الكيان", "entity_id": "رقم الكيان",
        "user_name": "المستخدم", "details": "التفاصيل",
        "created_at": "التاريخ",
    })
    st.dataframe(frame, width="stretch", hide_index=True)
