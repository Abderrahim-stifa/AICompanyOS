"""الوكلاء السبعة — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, page_role_agents


render_page(get_company(), page_role_agents)
