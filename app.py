import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL COMPLETA (WHITE-LABEL)
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

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
    st.error("Erro na conexão segura de dados. Atualize a página.")
    st.stop()

# ==========================================
# HELPERS ANTI-QUEBRA
# ==========================================
def safe_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except:
        return float(default)

def safe_int(value, default=0):
    try:
        if value is None:
            return int(default)
        return int(value)
    except:
        return int(default)

# ==========================================
# FUNCTIONS DE GERENCIAMENTO DE ESTADOS
# ==========================================
def inicializar_estrategia_vazia():
    st.session_state['nome_estrategia_atual'] = ""
    st.session_state['historico_rolagens'] = []
    st.session_state['ciclo_nome'] = f"Série {datetime.date.today().strftime('%b/%y')}"

    st.session_state['val_preco_acao'] = 0.0
    st.session_state['val_qtd'] = 0

    st.session_state['val_ticker_put'] = ""
    st.session_state['val_preco_put'] = 0.0
    st.session_state['val_strike_put'] = 0.0

    st.session_state['val_ticker_call'] = ""
    st.session_state['val_strike_call'] = 0.0
    st.session_state['val_premio_call'] = 0.0

    st.session_state['val_dividendos'] = 0.0
    st.session_state['val_jscp'] = 0.0

    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

def carregar_estrategia_salva(nome, pkg):
    st.session_state['nome_estrategia_atual'] = nome
    st.session_state['historico_rolagens'] = pkg.get('historico_rolagens', [])
    st.session_state['ciclo_nome'] = pkg.get('ciclo_nome', f"Série {datetime.date.today().strftime('%b/%y')}")

    st.session_state['val_preco_acao'] = safe_float(pkg.get('preco_acao', 0.0))
    st.session_state['val_qtd'] = safe_int(pkg.get('qtd', 0))

    st.session_state['val_ticker_put'] = pkg.get('ticker_put', "")
    st.session_state['val_preco_put'] = safe_float(pkg.get('preco_put', 0.0))
    st.session_state['val_strike_put'] = safe_float(pkg.get('strike_put', 0.0))

    st.session_state['val_ticker_call'] = pkg.get('ticker_call', "")
    st.session_state['val_strike_call'] = safe_float(pkg.get('strike_call', 0.0))
    st.session_state['val_premio_call'] = safe_float(pkg.get('premio_call', 0.0))

    st.session_state['val_dividendos'] = safe_float(pkg.get('dividendos', 0.0))
    st.session_state['val_jscp'] = safe_float(pkg.get('jscp', 0.0))

    vencimento = pkg.get('val_data_vencimento')

    if vencimento:
        try:
            st.session_state['val_data_vencimento'] = datetime.datetime.strptime(
                vencimento,
                "%Y-%m-%d"
            ).date()
        except:
            st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)
    else:
        st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

# ==========================================
# MOTOR BRAPI
# ==========================================
def buscar_dados_opcao_brapi(ticker):
    if not ticker:
        return None

    token = st.secrets.get("BRAPI_TOKEN", "")

    if not token:
        st.error("🚨 BRAPI_TOKEN não encontrado nos Secrets.")
        return None

    url = f"https://brapi.dev/api/quote/{ticker.upper()}?token={token}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 401:
            st.error("🚨 Token BrAPI inválido.")
            return None

        elif response.status_code == 404:
            st.warning(f"⚠️ Ticker '{ticker.upper()}' não encontrado.")
            return None

        elif response.status_code != 200:
            st.error(f"🚨 Erro BrAPI: {response.status_code}")
            return None

        data = response.json()

        if "results" not in data or len(data["results"]) == 0:
            st.warning("⚠️ API retornou vazio.")
            return None

        ativo = data["results"][0]

        preco = safe_float(ativo.get("regularMarketPrice", 0.0))
        strike = safe_float(ativo.get("strikePrice", 0.0))
        vencimento_str = ativo.get("expirationDate", "")

        vencimento_date = None

        if vencimento_str:
            try:
                vencimento_date = datetime.datetime.strptime(
                    vencimento_str[:10],
                    "%Y-%m-%d"
                ).date()
            except:
                vencimento_date = None

        return {
            "preco": preco,
            "strike": strike,
            "vencimento": vencimento_date
        }

    except requests.exceptions.RequestException as e:
        st.error(f"🚨 Erro de rede: {e}")
        return None

# ==========================================
# SESSION STATE
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'username' not in st.session_state:
    st.session_state['username'] = ""

if 'preco_acao_tela' not in st.session_state:
    st.session_state['preco_acao_tela'] = 0.0

# ==========================================
# LOGIN TOKEN
# ==========================================
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
                st.session_state['dados_nuvem'] = db_res.data[0].get(
                    "dados",
                    {"estrategias": {}}
                )
            else:
                st.session_state['dados_nuvem'] = {"estrategias": {}}

            st.session_state['projeto_index'] = 0
            inicializar_estrategia_vazia()

    except:
        pass

# ==========================================
# LOGIN PAGE
# ==========================================
if not st.session_state['logged_in']:

    with st.container():

        col_logo, col_titulo = st.columns([1, 8])

        with col_logo:
            st.title("🦅")

        with col_titulo:
            st.title("Gouldian Invest")
            st.markdown("Plataforma Quantitativa de Engenharia Financeira de Derivativos.")

    st.divider()

    col_login, col_vazia = st.columns([1, 2])

    with col_login:

        with st.container(border=True):

            st.subheader("Painel de Acesso")

            modo = st.radio(
                "Selecione sua ação:",
                ["Login", "Criar Conta", "Esqueci a Senha"],
                horizontal=True
            )

            if modo in ["Login", "Criar Conta"]:

                email_input = st.text_input(
                    "E-mail corporativo ou pessoal"
                ).strip().lower()

                senha_input = st.text_input(
                    "Senha",
                    type="password"
                )

                if modo == "Login":

                    if st.button(
                        "Entrar na Plataforma",
                        type="primary",
                        use_container_width=True
                    ):

                        if email_input and senha_input:

                            try:
                                auth_response = supabase.auth.sign_in_with_password({
                                    "email": email_input,
                                    "password": senha_input
                                })

                                st.session_state['logged_in'] = True
                                st.session_state['username'] = email_input.split('@')[0].capitalize()
                                st.session_state['user_email_completo'] = email_input

                                st.query_params["access_token"] = auth_response.session.access_token

                                db_res = supabase.table("usuarios").select("*").eq("email", email_input).execute()

                                if len(db_res.data) > 0:
                                    st.session_state['dados_nuvem'] = db_res.data[0].get(
                                        "dados",
                                        {"estrategias": {}}
                                    )
                                else:
                                    st.session_state['dados_nuvem'] = {"estrategias": {}}

                                    supabase.table("usuarios").insert({
                                        "email": email_input,
                                        "dados": st.session_state['dados_nuvem']
                                    }).execute()

                                st.session_state['projeto_index'] = 0

                                inicializar_estrategia_vazia()

                                st.rerun()

                            except Exception:
                                st.error("Erro de autenticação.")

                        else:
                            st.warning("Preencha todos os campos.")

                elif modo == "Criar Conta":

                    if st.button(
                        "Concluir Cadastro e Entrar",
                        type="primary",
                        use_container_width=True
                    ):

                        if email_input and senha_input:

                            try:
                                auth_response = supabase.auth.sign_up({
                                    "email": email_input,
                                    "password": senha_input
                                })

                                if auth_response.session:
                                    st.session_state['logged_in'] = True
                                    st.session_state['username'] = email_input.split('@')[0].capitalize()
                                    st.session_state['user_email_completo'] = email_input

                                    st.query_params["access_token"] = auth_response.session.access_token

                                st.session_state['dados_nuvem'] = {"estrategias": {}}

                                supabase.table("usuarios").insert({
                                    "email": email_input,
                                    "dados": st.session_state['dados_nuvem']
                                }).execute()

                                st.success("🎉 Conta criada com sucesso!")

                                st.rerun()

                            except Exception:
                                st.error("Falha no cadastro.")

            elif modo == "Esqueci a Senha":
                st.info("🔧 Recuperação temporariamente indisponível.")

    st.stop()

# ==========================================
# GARANTIA DE SESSION STATE
# ==========================================
if 'val_data_vencimento' not in st.session_state:
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

# ==========================================
# HEADER
# ==========================================
with st.container():

    c_header1, c_header2 = st.columns([8, 2])

    with c_header1:
        st.title("Gouldian Invest | Gestão de Collar Dinâmico")

        st.write(
            f"Sessão Ativa: **{st.session_state['username']}** | "
            f"Conexão Segura e Criptografada 🛡️"
        )

    with c_header2:

        st.write("")

        if st.button(
            "Sair (Logout) 🚪",
            use_container_width=True
        ):

            supabase.auth.sign_out()

            st.session_state['logged_in'] = False

            st.query_params.clear()

            st.rerun()

# ==========================================
# PERFIL
# ==========================================
with st.expander("👤 Meu Perfil & Carteira de Estratégias", expanded=True):

    dict_estrategias = st.session_state['dados_nuvem'].get("estrategias", {})

    opcoes_projeto = [
        "-- Criar Nova Estratégia (Tela Limpa) --"
    ] + list(dict_estrategias.keys())

    if 'projeto_index' not in st.session_state:
        st.session_state['projeto_index'] = 0

    projeto_escolhido = st.selectbox(
        "📁 Selecione o Projeto / Estratégia em andamento:",
        opcoes_projeto,
        index=st.session_state['projeto_index']
    )

    if (
        'ultimo_projeto_escolhido' not in st.session_state
        or st.session_state['ultimo_projeto_escolhido'] != projeto_escolhido
    ):

        st.session_state['ultimo_projeto_escolhido'] = projeto_escolhido

        st.session_state['projeto_index'] = opcoes_projeto.index(projeto_escolhido)

        if projeto_escolhido == "-- Criar Nova Estratégia (Tela Limpa) --":
            inicializar_estrategia_vazia()
        else:
            carregar_estrategia_salva(
                projeto_escolhido,
                dict_estrategias[projeto_escolhido]
            )

        st.rerun()

st.divider()

# ==========================================
# CÁLCULO ACUMULADOS
# ==========================================
caixa_acumulado_calls = 0.0
caixa_proventos = 0.0

if st.session_state['historico_rolagens']:

    for linha in st.session_state['historico_rolagens']:

        caixa_acumulado_calls += safe_float(
            linha.get("Renda Opção Liq.", 0.0)
        )

        caixa_proventos += safe_float(
            linha.get("Dividendos/JSCP Liq.", 0.0)
        )

caixa_total_gerado = caixa_acumulado_calls + caixa_proventos

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.image(
    "https://cdn-icons-png.flaticon.com/512/2942/2942259.png",
    width=50
)

st.sidebar.header("🔍 Monitor de Cotação")

ticker_acao = st.sidebar.text_input(
    "Ticker da Ação",
    value="",
    placeholder="Ex: PETR4.SA"
)

st.sidebar.markdown(
    f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}"
)

if st.sidebar.button("Buscar Preço B3"):

    if ticker_acao:

        try:
            acao = yf.Ticker(ticker_acao)

            hist = acao.history(period="1d")

            if not hist.empty:
                preco_atual = hist['Close'].iloc[-1]

                st.session_state['preco_acao_tela'] = float(preco_atual)

                st.rerun()
            else:
                st.sidebar.error("Ativo sem dados.")

        except:
            st.sidebar.error("Ativo indisponível.")

# ==========================================
# FASE 1
# ==========================================
st.header("📦 Fase 1: Estrutura Principal da Operação")

with st.container(border=True):

    col_cron1, col_cron2, col_vazio_cron = st.columns([2, 2, 4])

    with col_cron1:

        ciclo_nome_input = st.text_input(
            "🔖 Identificador do Ciclo Atual",
            value=st.session_state['ciclo_nome']
        )

        st.session_state['ciclo_nome'] = ciclo_nome_input

    with col_cron2:

        data_montagem = st.date_input(
            "🗓️ Data Base (Início/Rolagem)",
            value=datetime.date.today(),
            format="DD/MM/YYYY"
        )

col1, col2, col3 = st.columns(3)

# ==========================================
# COLUNA AÇÃO
# ==========================================
with col1:

    with st.container(border=True):

        st.subheader("🏢 1. Ativo Base (Ação)")

        preco_acao_raw = st.number_input(
            "Preço de Aquisição (R$)",
            value=safe_float(st.session_state['val_preco_acao']),
            placeholder="0.00",
            format="%.2f"
        )

        qtd_raw = st.number_input(
            "Quantidade Exposta",
            value=safe_int(st.session_state['val_qtd']),
            placeholder="1000",
            step=100
        )

        preco_acao = safe_float(preco_acao_raw)
        qtd = safe_int(qtd_raw)

        st.session_state['val_preco_acao'] = preco_acao
        st.session_state['val_qtd'] = qtd

# ==========================================
# COLUNA PUT
# ==========================================
with col2:

    with st.container(border=True):

        st.subheader("🛡️ 2. Seguro Longo (Put)")

        c_put_tick, c_put_btn = st.columns([2, 1])

        with c_put_tick:

            ticker_put = st.text_input(
                "Ticker da Put",
                value=st.session_state['val_ticker_put'],
                placeholder="PETRR454"
            )

            st.session_state['val_ticker_put'] = ticker_put

        with c_put_btn:

            st.write("")
            st.write("")

            if st.button(
                "⚡ Buscar",
                key="btn_put",
                use_container_width=True
            ):

                dados_api = buscar_dados_opcao_brapi(ticker_put)

                if dados_api:

                    st.session_state['val_preco_put'] = dados_api['preco']

                    if dados_api['strike'] > 0:
                        st.session_state['val_strike_put'] = dados_api['strike']

                    st.toast("✅ Put carregada com sucesso!")

                    st.rerun()

        preco_put_raw = st.number_input(
            "Prêmio Pago (R$)",
            value=safe_float(st.session_state['val_preco_put']),
            placeholder="0.00",
            format="%.2f"
        )

        strike_put_raw = st.number_input(
            "Strike (R$)",
            value=safe_float(st.session_state['val_strike_put']),
            placeholder="0.00",
            format="%.2f"
        )

        preco_put = safe_float(preco_put_raw)
        strike_put = safe_float(strike_put_raw)

        st.session_state['val_preco_put'] = preco_put
        st.session_state['val_strike_put'] = strike_put

# ==========================================
# RESUMO
# ==========================================
volume_acao = preco_acao * qtd
volume_put = preco_put * qtd

with col3:

    with st.container(border=True):

        st.subheader("📊 3. Resumo Patrimonial")

        st.metric(
            "Capital Inicial Imobilizado",
            f"R$ {(volume_acao + volume_put):,.2f}"
        )

        st.metric(
            "Custo Médio Atual",
            f"R$ {(preco_acao + preco_put):,.2f}"
        )

        strike_minimo = preco_acao + preco_put

        st.info(
            f"🎯 Strike mínimo defensivo: R$ {strike_minimo:.2f}"
        )
