import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL COMPLETA
# ==========================================
st.set_page_config(page_title="Gouldian Invest Pro", page_icon="🦅", layout="wide")

REMOVER_BRANDING_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
"""
st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# ==========================================
# MOTOR DE BUSCA INSTITUCIONAL (BRAPI PRO)
# ==========================================
def buscar_dados_opcao_pro(ticker):
    """
    Motor de busca de dados reais da B3 utilizando API Pro.
    """
    token = st.secrets.get("BRAPI_TOKEN", "")
    if not token:
        st.error("🚨 ERRO: Token da BrAPI não encontrado nos Secrets.")
        return None
        
    url = f"https://brapi.dev/api/quote/{ticker.upper()}?token={token}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            st.error(f"Erro de conexão com API: {response.status_code}")
            return None
            
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            ativo = data["results"][0]
            return {
                "preco": float(ativo.get("regularMarketPrice", 0.0)),
                "strike": float(ativo.get("strikePrice", 0.0)),
                "vencimento": datetime.datetime.strptime(ativo.get("expirationDate", "2026-01-01")[:10], "%Y-%m-%d").date()
            }
        return None
    except Exception as e:
        st.error(f"Erro no motor de busca: {e}")
        return None

# ==========================================
# GESTÃO DE ESTADOS
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

def resetar_tela():
    st.session_state.update({
        'preco_acao': 0.0, 'qtd': 0, 'ticker_put': "", 'preco_put': 0.0, 
        'strike_put': 0.0, 'ticker_call': "", 'strike_call': 0.0, 
        'premio_call': 0.0, 'data_venc': datetime.date.today() + datetime.timedelta(days=21)
    })

# ==========================================
# UI - PAINEL DE ACESSO
# ==========================================
if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest - Acesso Pro")
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar no Sistema"):
        try:
            supabase.auth.sign_in_with_password({"email": email, "password": senha})
            st.session_state['logged_in'] = True
            st.rerun()
        except:
            st.error("Credenciais inválidas.")
    st.stop()

# ==========================================
# UI - DASHBOARD PRINCIPAL
# ==========================================
st.title("Gerenciamento de Collar Dinâmico")

# Barra Lateral
with st.sidebar:
    st.header("⚙️ Configurações")
    corretagem = st.number_input("Corretagem Fixa (R$)", value=0.0)
    ir_opcoes = st.number_input("IR Opções (%)", value=15.0) / 100
    st.divider()
    st.header("🔍 Monitor de Cotação")
    ticker_base = st.text_input("Ticker Ação", "PETR4")
    if st.button("Atualizar Preço Base"):
        try:
            st.session_state['preco_acao_base'] = yf.Ticker(f"{ticker_base}.SA").history(period="1d")['Close'].iloc[-1]
        except:
            st.error("Erro na busca.")

# Painel de Entrada de Dados (Cards)
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("🏢 Ativo Base")
        p_acao = st.number_input("Preço da Ação", value=st.session_state.get('preco_acao_base', 0.0))
        qtd = st.number_input("Quantidade", value=1000)

with col2:
    with st.container(border=True):
        st.subheader("🛡️ Proteção (Put)")
        t_put = st.text_input("Ticker Put")
        if st.button("⚡ Buscar Put"):
            dados = buscar_dados_opcao_pro(t_put)
            if dados:
                st.session_state.update({'p_put': dados['preco'], 's_put': dados['strike']})
                st.rerun()
        st.number_input("Prêmio Put", value=st.session_state.get('p_put', 0.0))
        st.number_input("Strike Put", value=st.session_state.get('s_put', 0.0))

# Seção de Call
with st.container(border=True):
    st.subheader("🔄 Lançamento de Call")
    c1, c2 = st.columns([2, 1])
    t_call = c1.text_input("Ticker Call")
    if c2.button("⚡ Buscar Call Pro"):
        dados = buscar_dados_opcao_pro(t_call)
        if dados:
            st.session_state.update({'p_call': dados['preco'], 's_call': dados['strike'], 'd_venc': dados['vencimento']})
            st.rerun()
    
    col_c1, col_c2, col_c3 = st.columns(3)
    premio = col_c1.number_input("Prêmio Recebido", value=st.session_state.get('p_call', 0.0))
    strike = col_c2.number_input("Strike Call", value=st.session_state.get('s_call', 0.0))
    data_venc = col_c3.date_input("Vencimento", value=st.session_state.get('d_venc', datetime.date.today()))

# Resumo Final
st.divider()
st.subheader("📈 Resultado Projetado")
lucro = (premio * qtd) - corretagem
st.metric("Resultado Líquido Estimado", f"R$ {lucro:,.2f}")

if st.button("Sair (Logout) 🚪"):
    supabase.auth.sign_out()
    st.session_state['logged_in'] = False
    st.rerun()
