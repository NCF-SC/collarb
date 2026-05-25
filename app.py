import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO E TOKEN
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

BRAPI_TOKEN = "3WD8M26ENLPs6znVxxcZth"

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
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception:
    st.error("Erro na conexão com Supabase.")
    st.stop()

# ==========================================
# MOTOR V2 (BRAPI)
# ==========================================
def buscar_dados_opcao_v2(underlying, target_ticker):
    if not underlying or not target_ticker:
        st.warning("Informe o Ativo Base e o Ticker da Opção.")
        return None

    headers = {"Authorization": f"Bearer {BRAPI_TOKEN}"}
    url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying.upper()}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            st.error(f"Erro na API V2: {response.status_code}")
            return None

        data = response.json()
        series = data.get("series", [])

        # Filtra a série pelo símbolo correto
        opcao = next((item for item in series if item["symbol"] == target_ticker.upper()), None)
        
        if opcao:
            return {
                "preco": float(opcao.get("close", 0.0)),
                "strike": float(opcao.get("strike", 0.0)),
                "vencimento": datetime.datetime.strptime(opcao.get("expirationDate", "2026-01-01"), "%Y-%m-%d").date()
            }
        else:
            st.warning(f"Ticker {target_ticker} não encontrado na cadeia de {underlying}.")
            return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# ==========================================
# FUNÇÕES DE ESTADO
# ==========================================
def inicializar_estrategia_vazia():
    st.session_state.update({
        'nome_estrategia_atual': "", 'historico_rolagens': [],
        'val_preco_acao': 0.0, 'val_qtd': 0, 'val_ticker_put': "", 
        'val_preco_put': 0.0, 'val_strike_put': 0.0, 'val_ticker_call': "", 
        'val_strike_call': 0.0, 'val_premio_call': 0.0,
        'val_dividendos': 0.0, 'val_jscp': 0.0
    })

def carregar_estrategia_salva(nome, pkg):
    st.session_state.update({
        'nome_estrategia_atual': nome,
        'historico_rolagens': pkg.get('historico_rolagens', []),
        'val_preco_acao': pkg.get('preco_acao', 0.0),
        'val_qtd': pkg.get('qtd', 0),
        'val_ticker_put': pkg.get('ticker_put', ""),
        'val_preco_put': pkg.get('preco_put', 0.0),
        'val_strike_put': pkg.get('strike_put', 0.0),
        'val_ticker_call': pkg.get('ticker_call', ""),
        'val_strike_call': pkg.get('strike_call', 0.0),
        'val_premio_call': pkg.get('premio_call', 0.0),
        'val_dividendos': pkg.get('dividendos', 0.0),
        'val_jscp': pkg.get('jscp', 0.0)
    })

# ==========================================
# AUTH
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest - Login")
    email = st.text_input("Email")
    pwd = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        st.session_state.update({'logged_in': True, 'username': "User", 'dados_nuvem': {"estrategias": {}}})
        inicializar_estrategia_vazia()
        st.rerun()
    st.stop()

# ==========================================
# DASHBOARD
# ==========================================
st.title("Gouldian Invest | Gestão de Collar")

# SIDEBAR
ticker_base = st.sidebar.text_input("Ativo Base (ex: PETR4)", value="PETR4")
if st.sidebar.button("Buscar Preço"):
    st.session_state['preco_acao_tela'] = float(yf.Ticker(f"{ticker_base}.SA").history(period="1d")['Close'].iloc[-1] or 0.0)

# FASE 1
col1, col2, col3 = st.columns(3)
with col1:
    preco_raw = st.number_input("Preço Ação (R$)", value=float(st.session_state.get('val_preco_acao', 0.0)))
    qtd_raw = st.number_input("Quantidade", value=int(st.session_state.get('val_qtd', 0)))
    preco_acao = float(preco_raw or 0.0)
    qtd = int(qtd_raw or 0)

with col2:
    ticker_put = st.text_input("Ticker Put", value=st.session_state.get('val_ticker_put', ""))
    if st.button("Buscar Put"):
        dados = buscar_dados_opcao_v2(ticker_base, ticker_put)
        if dados:
            st.session_state['val_preco_put'] = dados['preco']
            st.session_state['val_strike_put'] = dados['strike']
            st.rerun()
    preco_put = float(st.session_state.get('val_preco_put', 0.0) or 0.0)
    st.write(f"Preço Put: R$ {preco_put:.2f}")

with col3:
    # Correção do erro TypeError: cálculo com segurança
    cap_inicial = (preco_acao * qtd) + (preco_put * qtd)
    st.metric("Capital Inicial", f"R$ {cap_inicial:,.2f}")

# FASE 2
st.subheader("⚡ Lançamento de Call")
ticker_call = st.text_input("Ticker da Call", value=st.session_state.get('val_ticker_call', ""))
if st.button("Buscar Call"):
    dados = buscar_dados_opcao_v2(ticker_base, ticker_call)
    if dados:
        st.session_state['val_premio_call'] = dados['preco']
        st.session_state['val_strike_call'] = dados['strike']
        st.rerun()

# FASE 4 (Gravação)
if st.button("💾 Gravar na Nuvem"):
    nome = "Estrategia_Principal"
    st.session_state['dados_nuvem']["estrategias"][nome] = {
        "preco_acao": preco_acao, "qtd": qtd, "ticker_put": ticker_put,
        "preco_put": preco_put, "ticker_call": ticker_call
    }
    supabase.table("usuarios").update({"dados": st.session_state['dados_nuvem']}).eq("email", st.session_state['user_email_completo']).execute()
    st.success("Salvo!")
