import streamlit as st
import os

def check_env_var():
    if "NVIDIA_API_KEY" not in os.environ:
        st.error("Please export your NVIDIA_API_KEY from the NVIDIA AI Playground to continue with LLMs/Embedding Models!", icon="🚨")
        st.stop()   
    