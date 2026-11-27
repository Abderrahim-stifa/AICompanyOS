"""العملاء — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, page_clients


render_page(get_company(), page_clients)
