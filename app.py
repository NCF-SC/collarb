import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL E API (BRAPI V2)
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
except Exception as e:
    st.error("Erro na conexão segura de dados. Atualize a página.")
    st.stop()

# ==========================================
# MOTOR DE BUSCA INSTITUCIONAL (BRAPI V2)
# ==========================================
def buscar_dados_opcao_v2(underlying, target_ticker):
    """
    Busca a cadeia de opções na brapi v2 via /options/chain.
    Requer o ativo base (underlying) para filtrar corretamente.
    """
    if not underlying or not target_ticker:
        st.warning("Preencha o Ticker do Ativo Base e o Ticker da Opção.")
        return None

    headers = {"Authorization": f"Bearer {BRAPI_TOKEN}"}
    url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying.upper()}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 401:
            st.error("Erro 401: Token da BrAPI inválido ou não autorizado.")
            return None
        elif response.status_code != 200:
            st.error(f"Erro {response.status_code}: Falha na API BrAPI.")
            return None

        data = response.json()
        series = data.get("series", [])

        # Localiza o ticker específico na cadeia (Chain)
        opcao_encontrada = next((item for item in series if item["symbol"] == target_ticker.upper()), None)
        
        if opcao_encontrada:
            # Parse da data
            vencimento_str = opcao_encontrada.get("expirationDate", "2026-01-01")
            vencimento_date = datetime.datetime.strptime(vencimento_str[:10], "%Y-%m-%d").date()
            
            return {
                "preco": opcao_encontrada.get("close", 0.0),
                "strike": opcao_encontrada.get("strike", 0.0),
                "vencimento": vencimento_date
            }
        else:
            st.warning(f"O ticker {target_ticker.upper()} não consta na chain de {underlying.upper()}.")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}")
        return None

# ==========================================
# FUNCTIONS DE GERENCIAMENTO DE ESTADOS
# ==========================================
def inicializar_estrategia_vazia():
    st.session_state['nome_estrategia_atual'] = ""
    st.session_state['historico_rolagens'] = []
    st.session_state['ciclo_nome'] = f"Série {datetime.date.today().strftime('%b/%y')}"
    st.session_state['val_preco_acao'] = None
    st.session_state['val_qtd'] = None
    st.session_state['val_ticker_put'] = ""
    st.session_state['val_preco_put'] = None
    st.session_state['val_strike_put'] = None
    st.session_state['val_ticker_call'] = ""
    st.session_state['val_strike_call'] = None
    st.session_state['val_premio_call'] = None
    st.session_state['val_dividendos'] = None
    st.session_state['val_jscp'] = None
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

def carregar_estrategia_salva(nome, pkg):
    st.session_state['nome_estrategia_atual'] = nome
    st.session_state['historico_rolagens'] = pkg.get('historico_rolagens', [])
    st.session_state['ciclo_nome'] = pkg.get('ciclo_nome', f"Série {datetime.date.today().strftime('%b/%y')}")
    st.session_state['val_preco_acao'] = pkg.get('preco_acao', None)
    st.session_state['val_qtd'] = pkg.get('qtd', None)
    st.session_state['val_ticker_put'] = pkg.get('ticker_put', "")
    st.session_state['val_preco_put'] = pkg.get('preco_put', None)
    st.session_state['val_strike_put'] = pkg.get('strike_put', None)
    st.session_state['val_ticker_call'] = pkg.get('ticker_call', "")
    st.session_state['val_strike_call'] = pkg.get('strike_call', None)
    st.session_state['val_premio_call'] = pkg.get('premio_call', None)
    st.session_state['val_dividendos'] = pkg.get('dividendos', None)
    st.session_state['val_jscp'] = pkg.get('jscp', None)
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

# ==========================================
# 1. CONTROLE DE AMBIENTE E SUPABASE AUTH
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'preco_acao_tela' not in st.session_state:
    st.session_state['preco_acao_tela'] = 0.0

# [Lógica de Autenticação mantida...]
if "access_token" in st.query_params and not st.session_state['logged_in']:
    token_jwt = st.query_params["access_token"]
    try:
        user_auth = supabase.auth.get_user(token_jwt)
        if user_auth and user_auth.user:
            email_logado = user_auth.user.email
            st.session_state['logged_in'] = True
            st.session_state['username'] = email_logado.split('@')[0].capitalize()
            st.session_state['user_email_completo'] = email_logado
            db_res = supabase.table("usuarios").select("*").eq("email", email_logado).execute()
            if len(db_res.data) > 0:
                st.session_state['dados_nuvem'] = db_res.data[0].get("dados", {"estrategias": {}})
            else:
                st.session_state['dados_nuvem'] = {"estrategias": {}}
            st.session_state['projeto_index'] = 0
            inicializar_estrategia_vazia()
    except:
        pass

if not st.session_state['logged_in']:
    with st.container():
        col_logo, col_titulo = st.columns([1, 8])
        with col_logo: st.title("🦅")
        with col_titulo: st.title("Gouldian Invest")
    st.divider()
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        with st.container(border=True):
            st.subheader("Painel de Acesso")
            modo = st.radio("Selecione sua ação:", ["Login", "Criar Conta"], horizontal=True)
            email_input = st.text_input("E-mail").strip().lower()
            senha_input = st.text_input("Senha", type="password")
            if st.button("Entrar / Cadastrar", type="primary", use_container_width=True):
                if email_input and senha_input:
                    try:
                        if modo == "Login":
                            auth_response = supabase.auth.sign_in_with_password({"email": email_input, "password": senha_input})
                        else:
                            auth_response = supabase.auth.sign_up({"email": email_input, "password": senha_input})
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = email_input.split('@')[0].capitalize()
                        st.session_state['user_email_completo'] = email_input
                        st.session_state['dados_nuvem'] = {"estrategias": {}}
                        st.rerun()
                    except:
                        st.error("Erro na autenticação.")
    st.stop()

# ==========================================
# 2. SEÇÃO DE PERFIL E GERENCIAMENTO
# ==========================================
with st.container():
    c_header1, c_header2 = st.columns([8, 2])
    with c_header1:
        st.title("Gouldian Invest | Gestão de Collar Dinâmico")
    with c_header2:
        if st.button("Sair (Logout) 🚪"):
            supabase.auth.sign_out()
            st.session_state['logged_in'] = False
            st.query_params.clear()
            st.rerun()

# [EXPANDER DE PERFIL - CARREGAMENTO DE PROJETOS]
with st.expander("👤 Meu Perfil & Carteira de Estratégias", expanded=True):
    dict_estrategias = st.session_state['dados_nuvem'].get("estrategias", {})
    opcoes_projeto = ["-- Criar Nova Estratégia (Tela Limpa) --"] + list(dict_estrategias.keys())
    if 'projeto_index' not in st.session_state: st.session_state['projeto_index'] = 0
    projeto_escolhido = st.selectbox("📁 Selecione o Projeto:", opcoes_projeto, index=st.session_state['projeto_index'])
    
    if 'ultimo_projeto_escolhido' not in st.session_state or st.session_state['ultimo_projeto_escolhido'] != projeto_escolhido:
        st.session_state['ultimo_projeto_escolhido'] = projeto_escolhido
        st.session_state['projeto_index'] = opcoes_projeto.index(projeto_escolhido)
        if projeto_escolhido == "-- Criar Nova Estratégia (Tela Limpa) --":
            inicializar_estrategia_vazia()
        else:
            carregar_estrategia_salva(projeto_escolhido, dict_estrategias[projeto_escolhido])
        st.rerun()

st.divider()

# ==========================================
# 3. BARRA LATERAL (MONITOR E CUSTOS)
# ==========================================
ticker_acao = st.sidebar.text_input("Ticker da Ação Base", value="PETR4")
st.sidebar.markdown(f"**Preço de Tela:** R$ {st.session_state['preco_acao_tela']:.2f}")
if st.sidebar.button("Buscar Preço B3"):
    try:
        acao = yf.Ticker(f"{ticker_acao}.SA")
        preco_atual = acao.history(period="1d")['Close'].iloc[-1]
        st.session_state['preco_acao_tela'] = float(preco_atual)
        st.rerun()
    except: st.sidebar.error("Ativo indisponível.")

# [PARÂMETROS DE CUSTOS - MANTIDOS COMO ORIGINAL]
with st.sidebar.expander("⚙️ Custos e Juros"):
    ir_opcoes = st.number_input("IR Opções (%)", value=15.0) / 100
    emol_acao = st.number_input("Emol. Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emol. Opção (%)", value=0.0375, format="%.4f") / 100
    juros_bruto_aa = st.number_input("Selic Bruta (% a.a.)", value=14.50) / 100

# ==========================================
# FASE 1: MONTAGEM DO MODELO
# ==========================================
st.header("📦 Fase 1: Estrutura Principal")
col1, col2, col3 = st.columns(3)

with col1:
    preco_acao_raw = st.number_input("Preço de Aquisição (R$)", value=st.session_state['val_preco_acao'])
    qtd_raw = st.number_input("Quantidade", value=st.session_state['val_qtd'])
    preco_acao = preco_acao_raw if preco_acao_raw else 0.0
    qtd = int(qtd_raw) if qtd_raw else 0

with col2:
    ticker_put = st.text_input("Ticker da Put", value=st.session_state['val_ticker_put'])
    if st.button("⚡ Buscar PUT (BrAPI V2)"):
        dados = buscar_dados_opcao_v2(ticker_acao, ticker_put)
        if dados:
            st.session_state['val_preco_put'] = dados['preco']
            st.session_state['val_strike_put'] = dados['strike']
            st.rerun()
    preco_put = st.number_input("Prêmio Put (R$)", value=st.session_state['val_preco_put'])
    strike_put = st.number_input("Strike Put (R$)", value=st.session_state['val_strike_put'])

with col3:
    st.metric("Capital Inicial", f"R$ {(preco_acao * qtd) + (preco_put * qtd):,.2f}")

# ==========================================
# FASE 2: Lançamentos
# ==========================================
st.header("⚡ Fase 2: Amortização Mensal")
ticker_call = st.text_input("Ticker da Call", value=st.session_state['val_ticker_call'])
if st.button("⚡ Buscar CALL (BrAPI V2)"):
    dados = buscar_dados_opcao_v2(ticker_acao, ticker_call)
    if dados:
        st.session_state['val_premio_call'] = dados['preco']
        st.session_state['val_strike_call'] = dados['strike']
        st.session_state['val_data_vencimento'] = dados['vencimento']
        st.rerun()

premio_call = st.number_input("Prêmio Call (R$)", value=st.session_state['val_premio_call'])
strike_call = st.number_input("Strike Call (R$)", value=st.session_state['val_strike_call'])

# ==========================================
# FASE 3: SIMULADOR DE PAYOFF
# ==========================================
st.header("🔮 Fase 3: Simulador")
preco_vencimento = st.slider("Preço no Vencimento (R$)", 0.0, float(preco_acao * 2.0), float(preco_acao))

# ==========================================
# FASE 4: SALVAMENTO
# ==========================================
st.divider()
st.header("⏳ Fase 4: Arquivamento")
if st.button("💾 Gravar Projeto na Nuvem"):
    dados_estrategia = {
        "preco_acao": preco_acao,
        "qtd": qtd,
        "ticker_put": ticker_put,
        "preco_put": preco_put,
        "strike_put": strike_put,
        "ticker_call": ticker_call,
        "strike_call": strike_call,
        "premio_call": premio_call,
        "historico_rolagens": st.session_state['historico_rolagens'],
        "ciclo_nome": st.session_state['ciclo_nome']
    }
    st.session_state['dados_nuvem']["estrategias"][st.session_state['nome_estrategia_atual']] = dados_estrategia
    supabase.table("usuarios").update({"dados": st.session_state['dados_nuvem']}).eq("email", st.session_state['user_email_completo']).execute()
    st.success("Salvo!")

# [Tabela de Auditoria MANTIDA DO ORIGINAL]
if st.session_state['historico_rolagens']:
    st.write("### Livro-Razão")
    st.dataframe(pd.DataFrame(st.session_state['historico_rolagens']))
