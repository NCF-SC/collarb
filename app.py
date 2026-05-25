import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO E API
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
    st.error("Erro na conexão segura de dados.")
    st.stop()

# ==========================================
# MOTOR V2 (INTEGRAÇÃO BRAPI)
# ==========================================
def buscar_dados_opcao_v2(underlying, target_ticker):
    """Busca dados na API v2 da brapi via Chain."""
    if not underlying or not target_ticker:
        st.warning("Informe o ativo base (ex: PETR4) e o ticker da opção.")
        return None

    headers = {"Authorization": f"Bearer {BRAPI_TOKEN}"}
    url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying.upper()}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            st.error(f"Erro na API v2: {response.status_code}")
            return None

        data = response.json()
        series = data.get("series", [])

        # Localiza o ticker específico na cadeia
        opcao = next((item for item in series if item["symbol"] == target_ticker.upper()), None)
        
        if opcao:
            # Formatando o retorno para ser compatível com o restante do seu app
            vencimento_date = datetime.datetime.strptime(opcao.get("expirationDate", "2026-01-01"), "%Y-%m-%d").date()
            return {
                "preco": opcao.get("close", 0.0),
                "strike": opcao.get("strike", 0.0),
                "vencimento": vencimento_date
            }
        else:
            st.warning(f"Ticker {target_ticker} não encontrado para o ativo {underlying}.")
            return None
    except Exception as e:
        st.error(f"Erro de rede: {e}")
        return None

# ==========================================
# FUNÇÕES DE ESTADO
# ==========================================
def inicializar_estrategia_vazia():
    st.session_state.update({
        'nome_estrategia_atual': "",
        'historico_rolagens': [],
        'ciclo_nome': f"Série {datetime.date.today().strftime('%b/%y')}",
        'val_preco_acao': 0.0, 'val_qtd': 0,
        'val_ticker_put': "", 'val_preco_put': 0.0, 'val_strike_put': 0.0,
        'val_ticker_call': "", 'val_strike_call': 0.0, 'val_premio_call': 0.0,
        'val_dividendos': 0.0, 'val_jscp': 0.0,
        'val_data_vencimento': datetime.date.today() + datetime.timedelta(days=21)
    })

def carregar_estrategia_salva(nome, pkg):
    st.session_state.update({
        'nome_estrategia_atual': nome,
        'historico_rolagens': pkg.get('historico_rolagens', []),
        'ciclo_nome': pkg.get('ciclo_nome', ""),
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
# LOGIN E UI
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# [Lógica de Login mantida...]
if not st.session_state['logged_in']:
    # (Inserir aqui o código do container de login fornecido anteriormente)
    st.title("Gouldian Invest - Login")
    email = st.text_input("Email")
    pwd = st.text_input("Senha", type="password")
    if st.button("Login"):
        st.session_state['logged_in'] = True
        st.session_state['username'] = "Usuário"
        st.session_state['dados_nuvem'] = {"estrategias": {}}
        inicializar_estrategia_vazia()
        st.rerun()
    st.stop()

# ==========================================
# PAINEL PRINCIPAL
# ==========================================
st.title("Gouldian Invest | Gestão de Collar Dinâmico")
ticker_acao = st.sidebar.text_input("Ativo Base (ex: PETR4)", value="PETR4")

# [Cálculos, Inputs de Estratégia...]
# (Mantendo a estrutura do seu código original...)

# ==========================================
# BOTÕES DE BUSCA ATUALIZADOS
# ==========================================
with st.expander("🛡️ 2. Seguro Longo (Put)"):
    ticker_put = st.text_input("Ticker da Put", value=st.session_state['val_ticker_put'])
    if st.button("Buscar Put"):
        dados = buscar_dados_opcao_v2(ticker_acao, ticker_put)
        if dados:
            st.session_state['val_preco_put'] = dados['preco']
            st.session_state['val_strike_put'] = dados['strike']
            st.rerun()

with st.expander("⚡ Lançamento de Call (Venda Coberta)"):
    ticker_call = st.text_input("Ticker da Call", value=st.session_state['val_ticker_call'])
    if st.button("Buscar Call"):
        dados = buscar_dados_opcao_v2(ticker_acao, ticker_call)
        if dados:
            st.session_state['val_premio_call'] = dados['preco']
            st.session_state['val_strike_call'] = dados['strike']
            st.session_state['val_data_vencimento'] = dados['vencimento']
            st.rerun()

# [Restante do código... manter a lógica de cálculos e renderização original]
