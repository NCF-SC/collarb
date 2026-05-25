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

# ==========================================
# MOTOR V2 (BRAPI) CORRIGIDO
# ==========================================
def buscar_dados_opcao_v2(underlying, target_ticker):
    """
    Busca vencimentos, depois a chain, para encontrar o ticker.
    Isso evita o erro 400 exigindo a expirationDate.
    """
    if not underlying or not target_ticker:
        st.warning("Informe o Ativo Base e o Ticker da Opção.")
        return None

    headers = {"Authorization": f"Bearer {BRAPI_TOKEN}"}
    underlying = underlying.upper().replace(".SA", "")

    # 1. Primeiro, pegar todos os vencimentos disponíveis para o ativo
    exp_url = f"https://brapi.dev/api/v2/options/expirations?underlying={underlying}"
    try:
        resp_exp = requests.get(exp_url, headers=headers, timeout=10)
        if resp_exp.status_code != 200:
            st.error(f"Erro ao buscar vencimentos: {resp_exp.status_code}")
            return None
        
        vencimentos = resp_exp.json().get("expirations", [])
        
        # 2. Iterar sobre os vencimentos para achar o ticker solicitado
        for data_venc in vencimentos:
            chain_url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying}&expirationDate={data_venc}"
            resp_chain = requests.get(chain_url, headers=headers, timeout=10)
            
            if resp_chain.status_code == 200:
                series = resp_chain.json().get("series", [])
                opcao = next((item for item in series if item["symbol"] == target_ticker.upper()), None)
                
                if opcao:
                    return {
                        "preco": float(opcao.get("close", 0.0)),
                        "strike": float(opcao.get("strike", 0.0)),
                        "vencimento": datetime.datetime.strptime(data_venc, "%Y-%m-%d").date()
                    }
        
        st.warning(f"Ticker {target_ticker} não encontrado em nenhum vencimento de {underlying}.")
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

# ==========================================
# LOGIN E UI
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest - Login")
    if st.button("Simular Login"): # Atalho para testes
        st.session_state.update({'logged_in': True, 'username': "User", 'dados_nuvem': {"estrategias": {}}})
        inicializar_estrategia_vazia()
        st.rerun()
    st.stop()

# ==========================================
# DASHBOARD
# ==========================================
st.title("Gouldian Invest | Gestão de Collar")
ticker_base = st.sidebar.text_input("Ativo Base (ex: PETR4)", value="PETR4")

# FASE 1
col1, col2, col3 = st.columns(3)
with col1:
    preco_acao = float(st.number_input("Preço Ação (R$)", value=float(st.session_state.get('val_preco_acao', 0.0))) or 0.0)
    qtd = int(st.number_input("Quantidade", value=int(st.session_state.get('val_qtd', 0))) or 0)

with col2:
    ticker_put = st.text_input("Ticker Put", value=st.session_state.get('val_ticker_put', ""))
    if st.button("Buscar Put"):
        dados = buscar_dados_opcao_v2(ticker_base, ticker_put)
        if dados:
            st.session_state['val_preco_put'] = dados['preco']
            st.session_state['val_strike_put'] = dados['strike']
            st.rerun()
    st.write(f"Preço Put: R$ {float(st.session_state.get('val_preco_put', 0.0) or 0.0):.2f}")

with col3:
    # Cálculo seguro (com verificação)
    preco_put = float(st.session_state.get('val_preco_put', 0.0) or 0.0)
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

st.write("---")
if st.button("Limpar Sessão"):
    st.session_state.clear()
    st.rerun()
