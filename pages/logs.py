"""سجل الأنشطة — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, show_logs_page


render_page(get_company(), show_logs_page)
