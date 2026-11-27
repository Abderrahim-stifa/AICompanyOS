"""المشاريع — AICompanyOS native Streamlit page."""
from core.page_views import get_company, render_page, page_projects


render_page(get_company(), page_projects)
