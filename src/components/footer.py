import streamlit as st
from config.app_config import PRIMARY_COLOR, SECONDARY_COLOR
import requests
import time

def get_github_stars():
    try:
        response = requests.get("https://api.github.com/repos/harshhh28/hia")
        if response.status_code == 200:
            return response.json()["stargazers_count"]
        return None
    except:
        return None

def show_footer(in_sidebar=False):
    # Cache the stars count for 1 hour
    @st.cache_data(ttl=3600)
    def get_cached_stars():
        return get_github_stars()
    
    stars_count = get_cached_stars()
    
    base_styles = f"""
        text-align: center;
        padding: 0.75rem;
        background: linear-gradient(to right, 
            rgba(25, 118, 210, 0.03), 
            rgba(100, 181, 246, 0.05), 
            rgba(25, 118, 210, 0.03)
        );
        border-top: 1px solid rgba(100, 181, 246, 0.15);
        margin-top: {'0' if in_sidebar else '2rem'};
        {'width: 100%' if not in_sidebar else ''};
        box-shadow: 0 -2px 10px rgba(100, 181, 246, 0.05);
    """
    
    st.markdown(
        f"""
        <div style='{base_styles}'>
            <p style='
                font-family: "Source Sans Pro", sans-serif;
                color: #64B5F6;
                font-size: 0.76rem;
                letter-spacing: 0.02em;
                margin: 0;
                opacity: 0.95;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 8px;
            '>
                <span style="
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    padding: 2px 8px;
                    border-radius: 4px;
                    background: rgba(100, 181, 246, 0.05);
                    transition: all 0.2s ease;
                ">
                    <a href='https://github.com/harshhh28/hia' 
                       target='_blank' 
                       style='
                           color: #64B5F6;
                           text-decoration: none;
                           font-weight: 500;
                           transition: all 0.2s ease;
                           display: inline-flex;
                           align-items: center;
                           gap: 4px;
                       '
                       onmouseover="this.style.color='{PRIMARY_COLOR}'; this.style.textDecoration='underline'"
                       onmouseout="this.style.color='#1976D2'; this.style.textDecoration='none'">
                        <span style="color: #64B5F6;">Contribute to</span>
                        <svg height="12" width="12" viewBox="0 0 16 16" fill="#64B5F6">
                            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                        </svg>
                        HIA
                        {f'<span style="display: inline-flex; align-items: center; gap: 4px; margin-left: 4px; color: #64B5F6;"><svg height="12" width="12" viewBox="0 0 16 16" fill="#64B5F6"><path d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"></path></svg>{stars_count}</span>' if stars_count is not None else ''}
                    </a>
                </span>
                <span style="
                    color: #1976D2;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    transition: all 0.2s ease;
                ">
                    <a href='https://harshgajjar.vercel.app' 
                       target='_blank' 
                       style='
                           color: #1976D2;
                           text-decoration: none;
                           font-weight: 600;
                           transition: all 0.2s ease;
                           display: inline-flex;
                           align-items: center;
                           gap: 4px;
                       '
                       onmouseover="this.style.color='{PRIMARY_COLOR}'; this.style.textDecoration='underline'"
                       onmouseout="this.style.color='#1976D2'; this.style.textDecoration='none'">
                       Created by Harsh Gajjar
                    </a>
                </span>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
