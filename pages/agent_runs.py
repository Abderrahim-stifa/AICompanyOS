"""موافقات تشغيل الوكلاء — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, page_agent_runs


render_page(get_company(), page_agent_runs)
