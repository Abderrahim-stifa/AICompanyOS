"""سجل التعديلات — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, show_audit_page


render_page(get_company(), show_audit_page)
