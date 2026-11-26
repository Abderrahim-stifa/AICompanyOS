"""Small reusable Streamlit interaction helpers."""
import streamlit as st


def notify_and_refresh(message):
    st.success(message)
    st.rerun()
