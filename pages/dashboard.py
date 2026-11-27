"""لوحة التحكم — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, page_dashboard


render_page(get_company(), page_dashboard)
