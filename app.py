import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client

# ==========================================
# CONFIG
# ==========================================

st.set_page_config(
    page_title="Gouldian Invest",
    page_icon="🦅",
    layout="wide"
)

REMOVER_BRANDING_CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}
</style>
"""

st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

# ==========================================
# SUPABASE
# ==========================================

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# ==========================================
# BRAPI CONFIG
# ==========================================

BRAPI_TOKEN = st.secrets["BRAPI_TOKEN"]

# ==========================================
# BRAPI HELPERS
# ==========================================

@st.cache_data(ttl=60)
def buscar_preco_acao_brapi(ticker):

    try:

        ticker = ticker.upper().strip()

        url = f"https://brapi.dev/api/quote/{ticker}?token={BRAPI_TOKEN}"

        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if "results" not in data:
            return None

        if len(data["results"]) == 0:
            return None

        ativo = data["results"][0]

        return float(ativo.get("regularMarketPrice", 0.0))

    except Exception:
        return None

# ==========================================
# BUSCA OPÇÕES BRAPI
# ==========================================

@st.cache_data(ttl=60)
def buscar_dados_opcao(ticker_opcao):

    if not ticker_opcao:
        return None

    try:

        ticker_upper = ticker_opcao.upper().strip()

        # ======================================
        # TENTA QUOTE DIRETO
        # ======================================

        url = f"https://brapi.dev/api/quote/{ticker_upper}?token={BRAPI_TOKEN}"

        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if "results" not in data:
            return None

        if len(data["results"]) == 0:
            return None

        ativo = data["results"][0]

        preco = float(ativo.get("regularMarketPrice", 0.0))

        strike = float(ativo.get("strikePrice", 0.0))

        vencimento = None

        vencimento_raw = ativo.get("expirationDate")

        if vencimento_raw:

            try:

                vencimento = datetime.datetime.fromtimestamp(
                    vencimento_raw
                ).date()

            except Exception:

                vencimento = (
                    datetime.date.today()
                    + datetime.timedelta(days=21)
                )

        else:

            vencimento = (
                datetime.date.today()
                + datetime.timedelta(days=21)
            )

        tipo = ativo.get("optionType", "OPCAO")

        return {
            "tipo": tipo,
            "preco": preco,
            "strike": strike,
            "vencimento": vencimento
        }

    except Exception:
        return None

# ==========================================
# SESSION STATE
# ==========================================

if "preco_acao_tela" not in st.session_state:
    st.session_state["preco_acao_tela"] = 0.0

if "val_preco_put" not in st.session_state:
    st.session_state["val_preco_put"] = None

if "val_strike_put" not in st.session_state:
    st.session_state["val_strike_put"] = None

if "val_preco_call" not in st.session_state:
    st.session_state["val_preco_call"] = None

if "val_strike_call" not in st.session_state:
    st.session_state["val_strike_call"] = None

if "val_data_vencimento" not in st.session_state:
    st.session_state["val_data_vencimento"] = (
        datetime.date.today()
        + datetime.timedelta(days=21)
    )

# ==========================================
# HEADER
# ==========================================

st.title("🦅 Gouldian Invest")
st.caption("Gestão Quantitativa de Collar Dinâmico")

# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.header("📈 Monitor B3")

ticker_acao = st.sidebar.text_input(
    "Ticker da ação",
    placeholder="PETR4"
)

if st.sidebar.button("Buscar Preço B3"):

    preco = buscar_preco_acao_brapi(ticker_acao)

    if preco:

        st.session_state["preco_acao_tela"] = preco

        st.sidebar.success(
            f"Preço encontrado: R$ {preco:.2f}"
        )

    else:

        st.sidebar.error(
            "Não foi possível encontrar o ativo."
        )

st.sidebar.metric(
    "Preço Atual",
    f"R$ {st.session_state['preco_acao_tela']:.2f}"
)

# ==========================================
# FASE 1
# ==========================================

st.header("📦 Estrutura da Operação")

col1, col2, col3 = st.columns(3)

# ==========================================
# AÇÃO
# ==========================================

with col1:

    st.subheader("🏢 Ativo Base")

    preco_acao = st.number_input(
        "Preço Médio",
        min_value=0.0,
        format="%.2f"
    )

    qtd = st.number_input(
        "Quantidade",
        min_value=0,
        step=100
    )

# ==========================================
# PUT
# ==========================================

with col2:

    st.subheader("🛡️ Put")

    c1, c2 = st.columns([2, 1])

    with c1:

        ticker_put = st.text_input(
            "Ticker Put",
            placeholder="PETRR30"
        )

    with c2:

        st.write("")
        st.write("")

        if st.button("Buscar Put"):

            dados_put = buscar_dados_opcao(ticker_put)

            if dados_put:

                st.session_state["val_preco_put"] = dados_put["preco"]

                st.session_state["val_strike_put"] = dados_put["strike"]

                st.success("Put carregada.")

            else:

                st.error("Put não encontrada.")

    preco_put = st.number_input(
        "Prêmio Put",
        value=(
            float(st.session_state["val_preco_put"])
            if st.session_state["val_preco_put"]
            else 0.0
        ),
        format="%.2f"
    )

    strike_put = st.number_input(
        "Strike Put",
        value=(
            float(st.session_state["val_strike_put"])
            if st.session_state["val_strike_put"]
            else 0.0
        ),
        format="%.2f"
    )

# ==========================================
# CALL
# ==========================================

with col3:

    st.subheader("🚀 Call")

    c1, c2 = st.columns([2, 1])

    with c1:

        ticker_call = st.text_input(
            "Ticker Call",
            placeholder="PETRF38"
        )

    with c2:

        st.write("")
        st.write("")

        if st.button("Buscar Call"):

            dados_call = buscar_dados_opcao(ticker_call)

            if dados_call:

                st.session_state["val_preco_call"] = dados_call["preco"]

                st.session_state["val_strike_call"] = dados_call["strike"]

                st.session_state["val_data_vencimento"] = (
                    dados_call["vencimento"]
                )

                st.success("Call carregada.")

            else:

                st.error("Call não encontrada.")

    premio_call = st.number_input(
        "Prêmio Call",
        value=(
            float(st.session_state["val_preco_call"])
            if st.session_state["val_preco_call"]
            else 0.0
        ),
        format="%.2f"
    )

    strike_call = st.number_input(
        "Strike Call",
        value=(
            float(st.session_state["val_strike_call"])
            if st.session_state["val_strike_call"]
            else 0.0
        ),
        format="%.2f"
    )

    data_vencimento = st.date_input(
        "Vencimento",
        value=st.session_state["val_data_vencimento"]
    )

# ==========================================
# CÁLCULOS
# ==========================================

st.divider()

st.header("🧮 Motor Financeiro")

if qtd > 0:

    custo_acao = preco_acao * qtd

    custo_put = preco_put * qtd

    receita_call = premio_call * qtd

    custo_total = custo_acao + custo_put

    strike_break_even = (
        (custo_total - receita_call)
        / qtd
    )

    colr1, colr2, colr3 = st.columns(3)

    with colr1:

        st.metric(
            "Capital Total",
            f"R$ {custo_total:,.2f}"
        )

    with colr2:

        st.metric(
            "Receita Call",
            f"R$ {receita_call:,.2f}"
        )

    with colr3:

        st.metric(
            "Break-even",
            f"R$ {strike_break_even:.2f}"
        )

# ==========================================
# PAYOFF
# ==========================================

st.divider()

st.header("🔮 Simulador de Payoff")

if qtd > 0:

    preco_vencimento = st.slider(
        "Preço no vencimento",
        min_value=0.0,
        max_value=float(preco_acao * 2 if preco_acao > 0 else 100),
        value=float(preco_acao if preco_acao > 0 else 10),
        step=0.1
    )

    # =========================
    # CENÁRIOS
    # =========================

    if (
        strike_call > 0
        and preco_vencimento >= strike_call
    ):

        cenario = "🚀 Exercício da Call"

        valor_final = strike_call * qtd

    elif (
        strike_put > 0
        and preco_vencimento <= strike_put
    ):

        cenario = "🛡️ Exercício da Put"

        valor_final = strike_put * qtd

    else:

        cenario = "⚖️ Manutenção"

        valor_final = preco_vencimento * qtd

    pnl = (
        valor_final
        + receita_call
        - custo_total
    )

    retorno = (
        pnl / custo_total * 100
        if custo_total > 0
        else 0
    )

    st.subheader(cenario)

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Lucro/Prejuízo",
            f"R$ {pnl:,.2f}"
        )

    with c2:

        st.metric(
            "Retorno %",
            f"{retorno:.2f}%"
        )

# ==========================================
# DEBUG BRAPI
# ==========================================

st.divider()

with st.expander("🧪 Teste BRAPI"):

    teste = st.text_input(
        "Ticker teste",
        value="PETR4"
    )

    if st.button("Testar API"):

        try:

            url = (
                f"https://brapi.dev/api/quote/"
                f"{teste}?token={BRAPI_TOKEN}"
            )

            response = requests.get(url)

            st.write("STATUS:", response.status_code)

            st.json(response.json())

        except Exception as e:

            st.error(str(e))
